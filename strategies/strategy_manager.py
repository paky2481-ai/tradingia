"""
Strategy Manager - orchestrates multiple strategies across all instruments.

Extended with:
  - AutoConfig (hourly regime detection, indicator selection, param tuning)
  - MetaLearner (combines LSTM, GBM, cycle, fundamental into final signal)
  - Dynamic strategy selection per symbol based on market regime
"""

import asyncio
from typing import Dict, List, Optional

import pandas as pd

from strategies.base_strategy import BaseStrategy, TradeSignal
from strategies.ai_strategy import AIStrategy
from strategies.technical_strategy import (
    TrendFollowingStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    ScalpingStrategy,
)
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="strategies.manager")


class StrategyManager:
    """
    Runs all active strategies on incoming market data, aggregates signals,
    and applies AI meta-learning to produce the final recommendation.
    """

    def __init__(self):
        # All available strategies, keyed by name
        self._strategy_map: Dict[str, BaseStrategy] = {
            "ai_ensemble":     AIStrategy(timeframe=settings.primary_timeframe),
            "trend_following": TrendFollowingStrategy(timeframe="1h"),
            "mean_reversion":  MeanReversionStrategy(timeframe="1h"),
            "breakout":        BreakoutStrategy(timeframe="1d"),
            "scalping":        ScalpingStrategy(),
        }

        # Lazy-load AutoConfig to avoid heavy imports at startup
        self._auto_config = None
        logger.info(f"Strategy manager loaded {len(self._strategy_map)} strategies")

    # ── Public API ────────────────────────────────────────────────────────

    async def evaluate(
        self,
        symbol: str,
        data_by_timeframe: Dict[str, pd.DataFrame],
        asset_type: str = "stock",
    ) -> List[TradeSignal]:
        """
        Evaluate strategies for a symbol.

        1. If auto-config retune interval elapsed: run full AI auto-config pipeline
        2. Select the strategy recommended by auto-config (or default to all)
        3. Run selected strategy + ai_ensemble in parallel
        4. Aggregate with meta-learner confirmation
        """
        auto_config = self._get_auto_config()
        primary_df = data_by_timeframe.get(settings.primary_timeframe)
        if primary_df is None or len(primary_df) < 50:
            return []

        # ── Auto-config (hourly retune) ────────────────────────────────
        if auto_config.should_retune(symbol):
            try:
                await auto_config.run(symbol, primary_df, asset_type)
            except Exception as e:
                logger.warning(f"AutoConfig failed for {symbol}: {e}")

        config = auto_config.get_result(symbol)

        # ── Select strategies to run ───────────────────────────────────
        strategies_to_run: List[BaseStrategy] = []

        if config is not None:
            recommended = config.recommended_strategy
            # Always run AI ensemble as baseline
            if recommended != "ai_ensemble":
                strat = self._strategy_map.get(recommended)
                if strat and strat.active:
                    strategies_to_run.append(strat)
            ai_strat = self._strategy_map.get("ai_ensemble")
            if ai_strat and ai_strat.active:
                strategies_to_run.append(ai_strat)
        else:
            # No config yet: run all strategies
            strategies_to_run = [s for s in self._strategy_map.values() if s.active]

        # ── Run strategies ─────────────────────────────────────────────
        all_signals: List[TradeSignal] = []
        for strategy in strategies_to_run:
            df = data_by_timeframe.get(strategy.timeframe)
            if df is None:
                df = primary_df
            if df is None or len(df) < 50:
                continue
            try:
                sigs = await asyncio.to_thread(strategy.generate_signals, symbol, df)
                for s in sigs:
                    if strategy.filter_signal(s, settings.ml.min_confidence):
                        all_signals.append(s)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} error on {symbol}: {e}")

        aggregated = self._aggregate(all_signals)

        # ── Meta-learner confirmation ──────────────────────────────────
        if config is not None and aggregated:
            aggregated = self._apply_meta(aggregated, config, primary_df)

        return aggregated

    async def evaluate_all(
        self,
        data: Dict[str, Dict[str, pd.DataFrame]],
    ) -> Dict[str, List[TradeSignal]]:
        """Evaluate all symbols in parallel."""
        asset_map = settings.asset_type_map
        tasks = {
            symbol: self.evaluate(
                symbol,
                timeframes,
                asset_type=asset_map.get(symbol, "stock"),
            )
            for symbol, timeframes in data.items()
        }
        results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)
        output = {}
        for symbol, result in zip(tasks.keys(), results_list):
            if isinstance(result, Exception):
                logger.error(f"Evaluation error for {symbol}: {result}")
            elif result:
                output[symbol] = result
        return output

    def get_auto_config_result(self, symbol: str):
        """Expose AutoConfigResult to GUI panels."""
        return self._get_auto_config().get_result(symbol)

    async def run_analysis(
        self, symbol: str, df: pd.DataFrame, asset_type: str = "stock"
    ):
        """
        Force immediate full analysis (used by GUI 'Run AI Analysis' button).
        Resets last_run so retune always runs.
        """
        auto_config = self._get_auto_config()
        # Force retune by clearing last_run
        auto_config._last_run.pop(symbol, None)
        return await auto_config.run(symbol, df, asset_type)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _aggregate(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """
        Aggregate multiple strategy signals.
        Multiple agreements boost confidence.
        Conflicting signals → keep only highest confidence.
        """
        if not signals:
            return []

        buy_signals = [s for s in signals if s.direction == "buy"]
        sell_signals = [s for s in signals if s.direction == "sell"]

        result = []

        if buy_signals:
            best_buy = max(buy_signals, key=lambda s: s.confidence)
            if len(buy_signals) > 1:
                bonus = min(0.1 * (len(buy_signals) - 1), 0.2)
                best_buy.confidence = min(best_buy.confidence + bonus, 1.0)
                best_buy.metadata["agreement"] = len(buy_signals)
            result.append(best_buy)

        if sell_signals:
            best_sell = max(sell_signals, key=lambda s: s.confidence)
            if len(sell_signals) > 1:
                bonus = min(0.1 * (len(sell_signals) - 1), 0.2)
                best_sell.confidence = min(best_sell.confidence + bonus, 1.0)
                best_sell.metadata["agreement"] = len(sell_signals)
            result.append(best_sell)

        # Conflict resolution
        if buy_signals and sell_signals:
            result = [max(result, key=lambda s: s.confidence)]

        return result

    def _apply_meta(
        self,
        signals: List[TradeSignal],
        config,
        df: pd.DataFrame,
    ) -> List[TradeSignal]:
        """
        Confirm or veto each signal using the MetaLearner.
        If meta-learner disagrees with a signal's direction, lower its confidence.
        If meta-learner agrees, boost confidence slightly.
        """
        try:
            auto_config = self._get_auto_config()
            meta = auto_config.get_meta_learner()

            # Build MetaInput from config
            from models.meta_learner import MetaInput
            from indicators.cycle_analysis import CycleFeatures

            # Get volume_ratio if available
            volume_ratio = 1.0
            if "volume_ratio" in df.columns:
                volume_ratio = float(df["volume_ratio"].iloc[-1])
            elif "volume" in df.columns and len(df) >= 20:
                vol = df["volume"].values
                volume_ratio = float(vol[-1] / (vol[-20:].mean() + 1e-10))

            cycle_features = {
                "hurst": config.hurst,
                "dominant_period": config.dominant_period,
                "cycle_phase_sin": 0.0,
                "cycle_phase_cos": 1.0,
                "volatility_ratio": 0.01,
            }

            meta_input = MetaInput(
                cycle_features=cycle_features,
                fundamental_score=config.fundamental_score,
                regime=config.regime,
                volume_ratio=volume_ratio,
            )

            meta_signal = meta.predict_from_inputs(meta_input)

            # Apply meta confirmation
            confirmed = []
            for sig in signals:
                if meta_signal.direction == sig.direction:
                    # Agreement: slight boost
                    sig.confidence = min(sig.confidence * 1.05, 1.0)
                    sig.metadata["meta_confirmed"] = True
                elif meta_signal.direction == "neutral":
                    sig.metadata["meta_confirmed"] = False
                else:
                    # Disagreement: reduce confidence
                    sig.confidence = sig.confidence * 0.80
                    sig.metadata["meta_confirmed"] = False

                sig.metadata["meta_direction"] = meta_signal.direction
                sig.metadata["meta_confidence"] = meta_signal.confidence
                sig.metadata["regime"] = config.regime
                sig.metadata["hurst"] = config.hurst
                sig.metadata["dominant_period"] = config.dominant_period

                if sig.confidence >= settings.ml.min_confidence:
                    confirmed.append(sig)

            return confirmed

        except Exception as e:
            logger.debug(f"Meta-learner apply error: {e}")
            return signals

    def _get_auto_config(self):
        """Lazy-load AutoConfig to defer heavy imports."""
        if self._auto_config is None:
            from models.auto_config import AutoConfig
            self._auto_config = AutoConfig()
        return self._auto_config
