"""
Auto-Configuration Engine

Every hour (configurable) performs:
  1. Market regime detection (cycle analysis)
  2. Fundamental score computation
  3. Indicator selection (AI-weighted for asset type + regime)
  4. Strategy selection based on regime
  5. Lightweight parameter tuning via walk-forward grid search
  6. MetaLearner training update if enough history exists

Designed to be called from StrategyManager.evaluate() when the retune
interval has elapsed.
"""

import asyncio
import itertools
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import settings
from indicators.cycle_analysis import CycleFeatures
from data.fundamental import FundamentalFeed, FundamentalScore, fundamental_feed
from models.indicator_selector import IndicatorSelector
from models.meta_learner import MetaLearner, MetaInput
from models.timeframe_selector import TimeframeSelector
from utils.logger import get_logger

logger = get_logger.bind(name="models.auto_config")


# ── Strategy parameter grids ───────────────────────────────────────────────────

_PARAM_GRIDS: Dict[str, Dict[str, List[Any]]] = {
    "trend_following": {
        "ema_fast": [7, 9, 12],
        "ema_slow": [18, 21, 26],
    },
    "mean_reversion": {
        "bb_std": [1.5, 2.0, 2.5],
        "rsi_oversold": [35, 40, 45],
    },
    "breakout": {
        "channel_period": [15, 20, 25],
        "volume_ratio_threshold": [1.3, 1.5, 1.8],
    },
    "scalping": {
        "rsi_period": [5, 7, 9],
        "stoch_k_period": [9, 14, 21],
    },
    "ai_ensemble": {},   # no tunable params, model retrained separately
}


@dataclass
class AutoConfigResult:
    symbol: str
    asset_type: str
    recommended_strategy: str
    active_indicators: List[str]
    indicator_weights: Dict[str, float]
    tuned_params: Dict[str, Any]
    regime: str
    hurst: float
    dominant_period: int
    fundamental_score: float
    oscillator_for_chart: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 0.5
    # Timeframe ottimale selezionato dall'AI per questo simbolo.
    # Stringa vuota = usa settings.primary_timeframe come fallback.
    optimal_timeframe: str = ""


class AutoConfig:
    """
    Orchestrates automatic configuration of strategies, indicators,
    and parameters. Retunes every `retune_interval_hours` hours per symbol.
    """

    def __init__(self):
        self._results: Dict[str, AutoConfigResult] = {}
        self._last_run: Dict[str, datetime] = {}
        self._selector = IndicatorSelector()
        self._meta = MetaLearner()
        self._tf_selector = TimeframeSelector()
        self._retune_interval = timedelta(
            hours=settings.autoconfig.retune_interval_hours
        )
        self._results_path = os.path.join(
            settings.ml.models_dir, "auto_config_results.pkl"
        )

        # Load persisted state (pkl files for fast access)
        self._selector.load()
        self._meta.load()
        self._load_results()
        # Lazy AI store (avoids import at module init)
        self._ai_store = None

    # ── Public API ────────────────────────────────────────────────────────

    async def run(
        self,
        symbol: str,
        df: pd.DataFrame,
        asset_type: str,
        data_by_tf: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> AutoConfigResult:
        """
        Full auto-configuration pipeline for a symbol.
        Updates internal state and returns a result.

        Parameters
        ----------
        data_by_tf : dict opzionale {tf: DataFrame} con più timeframe.
                     Se fornito, viene usato per selezionare il timeframe
                     ottimale tramite TimeframeSelector.
        """
        try:
            result = await self._pipeline(symbol, df, asset_type, data_by_tf)
        except Exception as e:
            logger.error(f"AutoConfig pipeline error for {symbol}: {e}")
            result = self._default_result(symbol, asset_type)

        self._results[symbol] = result
        self._last_run[symbol] = datetime.utcnow()
        self._save_results()
        # Persist to SQLite (fire-and-forget)
        asyncio.create_task(self._save_to_db(result))
        return result

    def should_retune(self, symbol: str) -> bool:
        """True if the retune interval has elapsed since last run."""
        if not settings.autoconfig.enabled:
            return False
        last = self._last_run.get(symbol)
        if last is None:
            return True
        return datetime.utcnow() - last >= self._retune_interval

    def get_result(self, symbol: str) -> Optional[AutoConfigResult]:
        return self._results.get(symbol)

    def get_optimal_timeframe(self, symbol: str) -> str:
        """
        Ritorna il timeframe ottimale per il simbolo selezionato dall'AI.
        Fallback a settings.primary_timeframe se non ancora calcolato.
        """
        result = self._results.get(symbol)
        if result and result.optimal_timeframe:
            return result.optimal_timeframe
        return settings.primary_timeframe

    def get_meta_learner(self) -> MetaLearner:
        return self._meta

    def get_indicator_selector(self) -> IndicatorSelector:
        return self._selector

    def record_outcome(
        self,
        meta_input: MetaInput,
        actual_direction: str,
        asset_type: str,
        regime: str,
        used_indicators: List[str],
    ) -> None:
        """
        Called after a trade is closed to update online learning.
        """
        correct = (
            meta_input.lstm_signal is not None
            and meta_input.lstm_signal.direction == actual_direction
        )
        self._selector.update_weights(asset_type, regime, used_indicators, correct)
        self._meta.online_update(meta_input, actual_direction)

        # Periodically save updated weights
        try:
            self._selector.save()
        except Exception:
            pass

    # ── Pipeline ──────────────────────────────────────────────────────────

    async def _pipeline(
        self,
        symbol: str,
        df: pd.DataFrame,
        asset_type: str,
        data_by_tf: Optional[Dict[str, pd.DataFrame]] = None,
    ) -> AutoConfigResult:
        # ── 0. Timeframe selection (se abilitato e dati multi-TF disponibili) ─
        optimal_tf = ""
        if settings.tf_selector.enabled and data_by_tf and len(data_by_tf) > 1:
            optimal_tf = await asyncio.to_thread(
                self._tf_selector.select, data_by_tf, symbol
            )

        # ── 1. Cycle analysis ──────────────────────────────────────────
        cycle = await asyncio.to_thread(
            CycleFeatures.compute_all,
            df,
            settings.cycle.hurst_max_window,
            settings.cycle.fft_max_period,
        )
        regime = cycle["regime"]
        hurst = cycle["hurst"]
        dominant_period = cycle["dominant_period"]

        # ── 2. Fundamental analysis ────────────────────────────────────
        fund_score = 0.0
        if asset_type in settings.fundamental.enabled_asset_types:
            try:
                fund_data = await fundamental_feed.get_fundamentals(symbol, asset_type)
                fund_score = FundamentalScore.compute(fund_data, asset_type)
            except Exception:
                fund_score = 0.0

        # ── 3. Indicator selection ─────────────────────────────────────
        # First compute all technical indicators if not already present
        df_ind = await asyncio.to_thread(self._ensure_indicators, df)
        # Merge cycle features as additional columns
        for k, v in cycle.items():
            if isinstance(v, (int, float)):
                df_ind[k] = v

        top_n = settings.autoconfig.top_n_indicators
        selected = self._selector.select(df_ind, asset_type, regime, top_n=top_n)
        oscillator = self._selector.get_top_oscillator(asset_type, regime)
        indicator_weights = {
            k: self._selector.get_weights(asset_type, regime).get(k, 0.0)
            for k in selected
        }

        # ── 4. Strategy selection ──────────────────────────────────────
        strategy = self._select_strategy(regime, asset_type, hurst, dominant_period)

        # ── 5. Parameter tuning ────────────────────────────────────────
        lookback = settings.autoconfig.param_grid_lookback_bars
        tuned = await asyncio.to_thread(
            self._tune_params, df.tail(lookback), strategy
        )

        # ── 6. Meta-learner training update ───────────────────────────
        if len(self._meta._history) >= settings.autoconfig.min_history_for_meta:
            try:
                await asyncio.to_thread(self._meta.train, df)
                self._meta.save()
            except Exception:
                pass

        return AutoConfigResult(
            symbol=symbol,
            asset_type=asset_type,
            recommended_strategy=strategy,
            active_indicators=list(selected.keys()),
            indicator_weights=indicator_weights,
            tuned_params=tuned,
            regime=regime,
            hurst=hurst,
            dominant_period=dominant_period,
            fundamental_score=fund_score,
            oscillator_for_chart=oscillator,
            confidence=min(0.5 + abs(hurst - 0.5) * 0.5, 0.95),
            optimal_timeframe=optimal_tf,
        )

    # ── Strategy selection ─────────────────────────────────────────────────

    def _select_strategy(
        self,
        regime: str,
        asset_type: str,
        hurst: float,
        dominant_period: int,
    ) -> str:
        """
        Rule-based strategy selection from regime + Hurst + asset type.
        """
        if regime == "trending" and hurst > 0.55:
            return "trend_following"
        elif regime == "cycling" and hurst < 0.45 and dominant_period <= 20:
            return "mean_reversion"
        elif regime == "cycling" and dominant_period > 20:
            return "breakout"
        elif regime == "choppy" and asset_type in ("crypto", "forex"):
            return "scalping"
        else:
            return "ai_ensemble"

    # ── Parameter tuning ──────────────────────────────────────────────────

    def _tune_params(self, df: pd.DataFrame, strategy_name: str) -> Dict:
        """
        Lightweight grid-search on recent data.
        Returns best-performing parameter combination.
        """
        grid = _PARAM_GRIDS.get(strategy_name, {})
        if not grid:
            return {}

        keys = list(grid.keys())
        values = list(grid.values())
        best_sharpe = -np.inf
        best_params: Dict = {k: v[1] for k, v in grid.items()}  # default = middle value

        for combo in itertools.product(*values):
            params = dict(zip(keys, combo))
            sharpe = self._backtest_params(df, strategy_name, params)
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params

        return best_params

    def _backtest_params(
        self, df: pd.DataFrame, strategy_name: str, params: Dict
    ) -> float:
        """
        Minimal backtest: compute returns for strategy signals on df
        with given params. Returns Sharpe ratio.
        """
        try:
            signals = self._simple_signals(df, strategy_name, params)
            if signals is None or len(signals) == 0:
                return -1.0

            close = df["close"].values
            n = len(close)
            returns = []
            in_trade = False
            entry_price = 0.0
            direction = 0

            for i in range(1, n):
                sig = signals[i] if i < len(signals) else 0
                if not in_trade and sig != 0:
                    in_trade = True
                    entry_price = close[i]
                    direction = sig
                elif in_trade and sig == -direction:
                    pct = (close[i] - entry_price) / entry_price * direction
                    returns.append(pct)
                    in_trade = False

            if len(returns) < 5:
                return -1.0

            r = np.array(returns)
            return float(r.mean() / (r.std() + 1e-10))

        except Exception:
            return -1.0

    def _simple_signals(
        self, df: pd.DataFrame, strategy_name: str, params: Dict
    ) -> Optional[np.ndarray]:
        """Generate simple rule-based signals for backtest."""
        try:
            close = df["close"].values.astype(float)
            n = len(close)
            signals = np.zeros(n, dtype=int)

            if strategy_name == "trend_following":
                fast = int(params.get("ema_fast", 9))
                slow = int(params.get("ema_slow", 21))
                ema_f = pd.Series(close).ewm(span=fast).mean().values
                ema_s = pd.Series(close).ewm(span=slow).mean().values
                for i in range(1, n):
                    if ema_f[i] > ema_s[i] and ema_f[i - 1] <= ema_s[i - 1]:
                        signals[i] = 1
                    elif ema_f[i] < ema_s[i] and ema_f[i - 1] >= ema_s[i - 1]:
                        signals[i] = -1

            elif strategy_name == "mean_reversion":
                std = float(params.get("bb_std", 2.0))
                rsi_os = float(params.get("rsi_oversold", 40))
                sma = pd.Series(close).rolling(20).mean().values
                sigma = pd.Series(close).rolling(20).std().values
                upper = sma + std * sigma
                lower = sma - std * sigma
                for i in range(1, n):
                    if close[i] < lower[i] and close[i - 1] >= lower[i - 1]:
                        signals[i] = 1
                    elif close[i] > upper[i] and close[i - 1] <= upper[i - 1]:
                        signals[i] = -1

            elif strategy_name == "breakout":
                cp = int(params.get("channel_period", 20))
                high = df["high"].values.astype(float) if "high" in df else close
                low = df["low"].values.astype(float) if "low" in df else close
                for i in range(cp, n):
                    hh = high[i - cp:i].max()
                    ll = low[i - cp:i].min()
                    if close[i] > hh:
                        signals[i] = 1
                    elif close[i] < ll:
                        signals[i] = -1

            return signals
        except Exception:
            return None

    # ── Helpers ────────────────────────────────────────────────────────────

    def _ensure_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to df if not already computed."""
        if "rsi_14" not in df.columns:
            try:
                from indicators.technical import TechnicalIndicators
                df = TechnicalIndicators.compute_all(df)
            except Exception:
                pass
        return df

    def _default_result(self, symbol: str, asset_type: str) -> AutoConfigResult:
        return AutoConfigResult(
            symbol=symbol,
            asset_type=asset_type,
            recommended_strategy="ai_ensemble",
            active_indicators=["rsi_14", "macd_hist", "bb_pct", "atr_14"],
            indicator_weights={},
            tuned_params={},
            regime="choppy",
            hurst=0.5,
            dominant_period=20,
            fundamental_score=0.0,
            oscillator_for_chart="rsi_14",
            confidence=0.5,
        )

    def _get_ai_store(self):
        if self._ai_store is None:
            try:
                from database.ai_store import ai_store
                self._ai_store = ai_store
            except Exception:
                self._ai_store = False
        return self._ai_store if self._ai_store else None

    async def _save_to_db(self, result: AutoConfigResult) -> None:
        store = self._get_ai_store()
        if store is None:
            return
        try:
            await store.save_config(result)
            await store.save_selector_weights(result.symbol, self._selector._weights)
            await store.save_meta_history(result.symbol, list(self._meta._history))
        except Exception as e:
            logger.debug(f"AutoConfig DB save error: {e}")

    def _save_results(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._results_path), exist_ok=True)
            with open(self._results_path, "wb") as f:
                pickle.dump({
                    "results": self._results,
                    "last_run": self._last_run,
                }, f)
        except Exception:
            pass

    def _load_results(self) -> None:
        if os.path.exists(self._results_path):
            try:
                with open(self._results_path, "rb") as f:
                    state = pickle.load(f)
                self._results = state.get("results", {})
                self._last_run = state.get("last_run", {})
            except Exception:
                pass
