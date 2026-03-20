"""
Meta-Learner - combines LSTM, GBM, cycle analysis and fundamental signals
into a single final trading decision.

Architecture:
  - Input: 13-feature vector from all sub-models + context
  - Model: SGDClassifier (LogisticRegression with partial_fit for online updates)
  - Training: walk-forward on internal history buffer (max 1000 samples)
  - Online update: after each trade outcome, update weights incrementally

Feature vector (13 dims):
  [lstm_buy_conf, lstm_sell_conf,
   gbm_buy_conf,  gbm_sell_conf,
   hurst,
   cycle_phase_sin, cycle_phase_cos,
   fundamental_score,
   regime_trending, regime_cycling, regime_choppy,
   volatility_ratio,
   volume_ratio]
"""

import os
import pickle
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler

from models.base_model import BaseModel, ModelSignal
from config.settings import settings


_FEATURE_NAMES = [
    "lstm_buy_conf",
    "lstm_sell_conf",
    "gbm_buy_conf",
    "gbm_sell_conf",
    "hurst",
    "cycle_phase_sin",
    "cycle_phase_cos",
    "fundamental_score",
    "regime_trending",
    "regime_cycling",
    "regime_choppy",
    "volatility_ratio",
    "volume_ratio",
]
N_FEATURES = len(_FEATURE_NAMES)


@dataclass
class MetaInput:
    """Container for all inputs to the MetaLearner."""
    lstm_signal: Optional[ModelSignal] = None
    gbm_signal: Optional[ModelSignal] = None
    cycle_features: Dict = field(default_factory=dict)
    fundamental_score: float = 0.0
    regime: str = "choppy"
    volume_ratio: float = 1.0


class MetaLearner(BaseModel):
    """
    Lightweight meta-learner that aggregates all signal sources.
    Extends BaseModel for consistent save/load interface.
    """

    name: str = "meta_learner"

    _LABEL_MAP = {-1: "sell", 0: "neutral", 1: "buy"}
    _LABEL_INV = {"sell": -1, "neutral": 0, "buy": 1}

    def __init__(self):
        # SGDClassifier supports partial_fit → online learning
        self._clf = SGDClassifier(
            loss="log_loss",
            max_iter=1,
            tol=None,
            warm_start=True,
            random_state=42,
            class_weight="balanced",
            learning_rate="adaptive",
            eta0=0.01,
        )
        self._scaler = StandardScaler()
        self._is_fitted = False
        self._history: Deque[Tuple[np.ndarray, int]] = deque(maxlen=1000)
        self._model_path = os.path.join(
            settings.ml.models_dir, "meta_learner.pkl"
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def predict_from_inputs(self, meta_input: MetaInput) -> ModelSignal:
        """
        Build feature vector from all sub-model signals and run meta prediction.
        Falls back to a weighted vote if the meta-model is not yet fitted.
        """
        fv = self._build_feature_vector(meta_input)

        if self._is_fitted:
            try:
                fv_scaled = self._scaler.transform(fv.reshape(1, -1))
                proba = self._clf.predict_proba(fv_scaled)[0]
                classes = list(self._clf.classes_)
                # Map class ints to direction strings
                scores: Dict[str, float] = {
                    self._LABEL_MAP.get(int(c), "neutral"): float(p)
                    for c, p in zip(classes, proba)
                }
            except Exception:
                scores = self._fallback_vote(meta_input)
        else:
            scores = self._fallback_vote(meta_input)

        direction, confidence = self._scores_to_signal(scores)

        return ModelSignal(
            direction=direction,
            confidence=round(confidence, 4),
            predicted_return=None,
            metadata={
                "source": "meta_learner",
                "scores": scores,
                "hurst": meta_input.cycle_features.get("hurst", 0.5),
                "regime": meta_input.regime,
                "dominant_period": meta_input.cycle_features.get("dominant_period", 0),
                "fundamental_score": meta_input.fundamental_score,
                "lstm_dir": meta_input.lstm_signal.direction if meta_input.lstm_signal else "neutral",
                "gbm_dir": meta_input.gbm_signal.direction if meta_input.gbm_signal else "neutral",
                "feature_names": _FEATURE_NAMES,
                "feature_values": fv.tolist(),
                "is_meta_fitted": self._is_fitted,
            },
        )

    def online_update(self, meta_input: MetaInput, actual_direction: str) -> None:
        """
        Incremental learning after a realised trade outcome.
        Called by AutoConfig after each closed trade.
        """
        fv = self._build_feature_vector(meta_input)
        label = self._LABEL_INV.get(actual_direction, 0)
        self._history.append((fv, label))

        if len(self._history) >= settings.autoconfig.min_history_for_meta:
            self._partial_fit_one(fv, label)

    def train(self, df: pd.DataFrame, **kwargs) -> Dict:
        """
        Walk-forward batch training on internal history buffer.
        Called periodically by AutoConfig.
        """
        if len(self._history) < settings.autoconfig.min_history_for_meta:
            return {"error": "insufficient history", "samples": len(self._history)}

        X = np.array([h[0] for h in self._history])
        y = np.array([h[1] for h in self._history])

        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        self._scaler.fit(X_train)
        X_tr_s = self._scaler.transform(X_train)
        X_te_s = self._scaler.transform(X_test)

        classes = np.array([-1, 0, 1])
        self._clf.partial_fit(X_tr_s, y_train, classes=classes)
        self._is_fitted = True

        accuracy = float(np.mean(self._clf.predict(X_te_s) == y_test))
        return {
            "samples_train": len(X_train),
            "samples_test": len(X_test),
            "accuracy": round(accuracy, 4),
        }

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """
        BaseModel interface - not used directly; use predict_from_inputs() instead.
        Returns neutral signal.
        """
        return ModelSignal(direction="neutral", confidence=0.0, predicted_return=None,
                           metadata={"note": "use predict_from_inputs"})

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def save(self) -> None:
        os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
        state = {
            "clf": self._clf,
            "scaler": self._scaler,
            "is_fitted": self._is_fitted,
            "history": list(self._history),
        }
        with open(self._model_path, "wb") as f:
            pickle.dump(state, f)

    def load(self) -> bool:
        if os.path.exists(self._model_path):
            try:
                with open(self._model_path, "rb") as f:
                    state = pickle.load(f)
                self._clf = state["clf"]
                self._scaler = state["scaler"]
                self._is_fitted = state["is_fitted"]
                self._history = deque(state.get("history", []), maxlen=1000)
                return True
            except Exception:
                pass
        return False

    # ── Internal helpers ───────────────────────────────────────────────────

    def _build_feature_vector(self, meta_input: MetaInput) -> np.ndarray:
        """Construct 13-dim feature vector from MetaInput."""
        def _conf(sig: Optional[ModelSignal], direction: str) -> float:
            if sig is None:
                return 0.0
            if sig.direction == direction:
                return float(sig.confidence)
            return 0.0

        regime = meta_input.regime
        cf = meta_input.cycle_features

        fv = np.array([
            _conf(meta_input.lstm_signal, "buy"),
            _conf(meta_input.lstm_signal, "sell"),
            _conf(meta_input.gbm_signal, "buy"),
            _conf(meta_input.gbm_signal, "sell"),
            float(cf.get("hurst", 0.5)),
            float(cf.get("cycle_phase_sin", 0.0)),
            float(cf.get("cycle_phase_cos", 1.0)),
            float(meta_input.fundamental_score),
            1.0 if regime == "trending" else 0.0,
            1.0 if regime == "cycling" else 0.0,
            1.0 if regime == "choppy" else 0.0,
            float(cf.get("volatility_ratio", 0.01)),
            float(meta_input.volume_ratio),
        ], dtype=np.float32)

        return np.clip(np.nan_to_num(fv, nan=0.0, posinf=1.0, neginf=-1.0), -10.0, 10.0)

    def _fallback_vote(self, meta_input: MetaInput) -> Dict[str, float]:
        """
        Weighted vote from sub-models when meta-model is not yet fitted.
        LSTM weight 0.4, GBM weight 0.4, fundamental tiebreaker 0.2.
        """
        scores = {"buy": 0.0, "sell": 0.0, "neutral": 0.0}

        for sig, weight in [
            (meta_input.lstm_signal, 0.40),
            (meta_input.gbm_signal, 0.40),
        ]:
            if sig is not None and sig.direction in scores:
                scores[sig.direction] += weight * sig.confidence

        # Fundamental tiebreaker
        fs = meta_input.fundamental_score
        if fs > 0.2:
            scores["buy"] += 0.20 * fs
        elif fs < -0.2:
            scores["sell"] += 0.20 * abs(fs)
        else:
            scores["neutral"] += 0.20

        return scores

    def _scores_to_signal(self, scores: Dict[str, float]) -> Tuple[str, float]:
        """Convert score dict to (direction, confidence)."""
        direction = max(scores, key=scores.get)
        confidence = float(scores[direction])
        # Neutral if no direction reaches min threshold
        if direction != "neutral" and confidence < settings.ml.min_confidence * 0.7:
            direction = "neutral"
            confidence = 0.0
        return direction, min(confidence, 1.0)

    def _partial_fit_one(self, fv: np.ndarray, label: int) -> None:
        try:
            fv_scaled = self._scaler.transform(fv.reshape(1, -1))
            classes = np.array([-1, 0, 1])
            self._clf.partial_fit(fv_scaled, [label], classes=classes)
            self._is_fitted = True
        except Exception:
            pass
