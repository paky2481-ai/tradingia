"""
Indicator Selector - AI-driven indicator selection per asset type and market regime.

Maintains per-(asset_type, regime) importance weights that are:
  1. Initialised from GradientBoosting feature importances (when a model is available)
  2. Updated with an exponential moving average after each prediction outcome
  3. Biased by asset-type and regime priors

Usage:
    selector = IndicatorSelector()
    selected = selector.select(df_with_indicators, asset_type="stock", regime="trending")
    # → Dict[indicator_name, pd.Series]

    # After getting a realised return:
    selector.update_weights("stock", "trending", list(selected.keys()), correct=True)
    selector.save()
"""

import os
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import settings


# ── Indicator catalogue ────────────────────────────────────────────────────────

# Map logical group → column names expected in a df after compute_all()
INDICATOR_GROUPS: Dict[str, List[str]] = {
    "trend": [
        "sma_20", "sma_50", "ema_9", "ema_21", "ema_50",
        "macd", "macd_signal", "macd_hist",
        "above_sma50", "above_sma200", "golden_cross",
    ],
    "momentum": [
        "rsi_14", "stoch_k", "stoch_d", "cci_20",
        "williams_r", "roc_12", "momentum_10", "mfi_14",
    ],
    "volatility": [
        "atr_14", "bb_pct", "bb_width", "hist_vol_20",
        "hl_ratio", "oc_ratio",
    ],
    "volume": [
        "obv", "vwap", "cmf_20", "volume_ratio",
    ],
    "cycle": [
        "hurst", "dominant_period", "cycle_phase_norm",
    ],
}

# Flatten for reverse lookup
_INDICATOR_TO_GROUP: Dict[str, str] = {
    ind: grp
    for grp, indicators in INDICATOR_GROUPS.items()
    for ind in indicators
}

ALL_INDICATORS: List[str] = [ind for inds in INDICATOR_GROUPS.values() for ind in inds]

# ── Asset-type priors (group weight offsets) ──────────────────────────────────

_ASSET_BIAS: Dict[str, Dict[str, float]] = {
    "stock":     {"trend": 0.30, "momentum": 0.30, "volatility": 0.20, "volume": 0.20, "cycle": 0.00},
    "forex":     {"trend": 0.40, "momentum": 0.30, "volatility": 0.20, "volume": 0.05, "cycle": 0.05},
    "crypto":    {"trend": 0.25, "momentum": 0.30, "volatility": 0.30, "volume": 0.15, "cycle": 0.00},
    "commodity": {"trend": 0.20, "momentum": 0.20, "volatility": 0.20, "volume": 0.10, "cycle": 0.30},
    "index":     {"trend": 0.35, "momentum": 0.25, "volatility": 0.20, "volume": 0.10, "cycle": 0.10},
}

# ── Regime bias (additive delta to group weights) ─────────────────────────────

_REGIME_DELTA: Dict[str, Dict[str, float]] = {
    "trending": {"trend":  +0.20, "momentum": +0.10, "cycle": -0.15, "volume":  0.00, "volatility": -0.05},
    "cycling":  {"cycle":  +0.25, "momentum": +0.10, "trend": -0.15, "volume":  0.00, "volatility":  0.00},
    "choppy":   {"volatility": +0.20, "volume": +0.10, "trend": -0.10, "cycle": -0.10, "momentum": -0.05},
}


def _uniform_weights() -> Dict[str, float]:
    return {ind: 1.0 / len(ALL_INDICATORS) for ind in ALL_INDICATORS}


class IndicatorSelector:
    """
    Selects the most relevant technical indicators for a given
    (asset_type, regime) pair and adapts weights based on prediction outcomes.
    """

    EWM_ALPHA = 0.05        # slow adaptation (≈20-sample memory)
    CORRECT_BONUS = 0.10    # weight multiplier on correct prediction
    WRONG_PENALTY = 0.05    # weight reduction on wrong prediction

    def __init__(self):
        # weights[asset_type][regime][indicator] → float
        self._weights: Dict[str, Dict[str, Dict[str, float]]] = {}
        self._model_path: str = os.path.join(
            settings.ml.models_dir, "indicator_selector.pkl"
        )

    # ── Public API ────────────────────────────────────────────────────────

    def select(
        self,
        df: pd.DataFrame,
        asset_type: str,
        regime: str,
        top_n: int = 8,
    ) -> Dict[str, pd.Series]:
        """
        Return top_n indicators (name → last value Series) ordered by weight.
        Only indicators that actually exist as columns in df are returned.
        """
        weights = self._get_weights(asset_type, regime)

        # Filter to indicators present in df
        available = {k: v for k, v in weights.items() if k in df.columns}

        if not available:
            # Fallback: return whatever columns match our catalogue
            available = {
                col: 1.0 / top_n
                for col in df.columns
                if col in _INDICATOR_TO_GROUP
            }

        # Sort by weight descending, take top_n
        ranked = sorted(available.items(), key=lambda x: x[1], reverse=True)[:top_n]

        result: Dict[str, pd.Series] = {}
        for name, _ in ranked:
            if name in df.columns:
                result[name] = df[name]

        return result

    def get_weights(self, asset_type: str, regime: str) -> Dict[str, float]:
        """Return current weight dict for a (asset_type, regime) pair."""
        return dict(self._get_weights(asset_type, regime))

    def get_top_oscillator(self, asset_type: str, regime: str) -> str:
        """Return the single best oscillator name for the chart sub-panel."""
        oscillators = ["rsi_14", "macd_hist", "stoch_k", "cci_20", "mfi_14"]
        weights = self._get_weights(asset_type, regime)
        best = max(oscillators, key=lambda o: weights.get(o, 0.0))
        return best

    def update_weights(
        self,
        asset_type: str,
        regime: str,
        used_indicators: List[str],
        correct: bool,
    ) -> None:
        """
        EWM update after a prediction outcome.
        Correct → slightly boost used indicators.
        Wrong   → slightly penalise used indicators.
        """
        weights = self._get_weights(asset_type, regime)
        delta = self.CORRECT_BONUS if correct else -self.WRONG_PENALTY

        for ind in used_indicators:
            if ind in weights:
                weights[ind] = float(np.clip(
                    weights[ind] * (1.0 + delta * self.EWM_ALPHA),
                    1e-6,
                    1.0,
                ))

        # Renormalise
        total = sum(weights.values()) or 1.0
        for ind in weights:
            weights[ind] /= total

    def load_from_gbm_model(self, gbm_model) -> None:
        """
        Seed indicator weights from a trained GradientBoosting model's
        feature_importances_.  Overwrites existing learned weights.
        """
        try:
            fi = gbm_model.feature_importances_
            features = gbm_model.feature_names_in_  # sklearn attribute
        except AttributeError:
            return

        imp_map = dict(zip(features, fi))

        for asset_type in _ASSET_BIAS:
            for regime in ("trending", "cycling", "choppy"):
                w = self._get_weights(asset_type, regime)
                for ind, imp in imp_map.items():
                    if ind in w:
                        w[ind] = float(imp)
                # Renormalise
                total = sum(w.values()) or 1.0
                for ind in w:
                    w[ind] /= total

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
        with open(self._model_path, "wb") as f:
            pickle.dump(self._weights, f)

    def load(self) -> bool:
        if os.path.exists(self._model_path):
            try:
                with open(self._model_path, "rb") as f:
                    self._weights = pickle.load(f)
                return True
            except Exception:
                pass
        return False

    # ── Internal helpers ──────────────────────────────────────────────────

    def _get_weights(self, asset_type: str, regime: str) -> Dict[str, float]:
        """Return (and initialise if needed) the weight dict for (asset_type, regime)."""
        if asset_type not in self._weights:
            self._weights[asset_type] = {}
        if regime not in self._weights[asset_type]:
            self._weights[asset_type][regime] = self._build_prior(asset_type, regime)
        return self._weights[asset_type][regime]

    def _build_prior(self, asset_type: str, regime: str) -> Dict[str, float]:
        """
        Build initial weights from asset-type + regime biases.
        Each indicator gets the group weight / group size.
        """
        asset_bias = _ASSET_BIAS.get(asset_type, _ASSET_BIAS["stock"])
        regime_delta = _REGIME_DELTA.get(regime, {})

        # Combine
        group_weights = {}
        for grp in INDICATOR_GROUPS:
            w = asset_bias.get(grp, 0.10) + regime_delta.get(grp, 0.0)
            group_weights[grp] = max(w, 0.01)

        # Distribute group weight evenly among its indicators
        weights: Dict[str, float] = {}
        for grp, grp_w in group_weights.items():
            inds = INDICATOR_GROUPS[grp]
            per_ind = grp_w / len(inds)
            for ind in inds:
                weights[ind] = per_ind

        # Normalise
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}
