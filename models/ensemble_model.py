"""
Ensemble model that combines RandomForest + LSTM + rule-based signals
via weighted voting for robust predictions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from models.base_model import BaseModel, ModelSignal
from models.random_forest_model import RandomForestModel
from models.lstm_model import LSTMModel
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="models.ensemble")


class EnsembleModel(BaseModel):
    """
    Combines multiple models with configurable weights.
    Automatically falls back if sub-models not trained.
    """

    def __init__(self, name: str = "ensemble"):
        super().__init__(name)
        self.rf_model = RandomForestModel(name=f"{name}_rf")
        self.lstm_model = LSTMModel(name=f"{name}_lstm")
        self.weights = {"rf": 0.5, "lstm": 0.5}

    def prepare_features(self, df: pd.DataFrame):
        # Not used directly — delegates to sub-models
        return None, None

    def train(self, df: pd.DataFrame) -> Dict:
        logger.info("Training ensemble sub-models...")
        rf_metrics = self.rf_model.train(df)
        lstm_metrics = self.lstm_model.train(df)
        self.is_trained = True
        return {"rf": rf_metrics, "lstm": lstm_metrics}

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        signals: List[ModelSignal] = []
        weights: List[float] = []

        # Collect sub-model predictions
        try:
            rf_signal = self.rf_model.predict(df)
            if rf_signal.confidence > 0:
                signals.append(rf_signal)
                weights.append(self.weights["rf"])
        except Exception as e:
            logger.warning(f"RF predict error: {e}")

        try:
            lstm_signal = self.lstm_model.predict(df)
            if lstm_signal.confidence > 0:
                signals.append(lstm_signal)
                weights.append(self.weights["lstm"])
        except Exception as e:
            logger.warning(f"LSTM predict error: {e}")

        if not signals:
            return ModelSignal("neutral", 0.0)

        # Weighted vote
        direction_scores: Dict[str, float] = {"buy": 0.0, "sell": 0.0, "neutral": 0.0}
        total_w = sum(weights)

        for sig, w in zip(signals, weights):
            norm_w = w / total_w
            direction_scores[sig.direction] += sig.confidence * norm_w

        best_direction = max(direction_scores, key=direction_scores.__getitem__)
        best_confidence = direction_scores[best_direction]

        # Agreement bonus: if all models agree, boost confidence
        if len(signals) > 1:
            all_agree = all(s.direction == best_direction for s in signals)
            if all_agree:
                best_confidence = min(best_confidence * 1.1, 1.0)

        return ModelSignal(
            direction=best_direction,
            confidence=best_confidence,
            metadata={
                "direction_scores": direction_scores,
                "num_models": len(signals),
                "models": [s.direction for s in signals],
            },
        )

    def save(self):
        self.rf_model.save()
        self.lstm_model.save()

    def load(self) -> bool:
        rf_ok = self.rf_model.load()
        lstm_ok = self.lstm_model.load()
        self.is_trained = rf_ok or lstm_ok
        return self.is_trained
