"""Base class for all AI/ML trading models"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict
import numpy as np
import pandas as pd
import os
import pickle
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="models")


class ModelSignal:
    """Output from a model prediction."""
    def __init__(
        self,
        direction: str,         # "buy", "sell", "neutral"
        confidence: float,      # 0.0 - 1.0
        predicted_return: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ):
        self.direction = direction
        self.confidence = confidence
        self.predicted_return = predicted_return
        self.metadata = metadata or {}

    def __repr__(self):
        return f"ModelSignal({self.direction}, conf={self.confidence:.2f})"


class BaseModel(ABC):
    """Abstract base for all trading models."""

    def __init__(self, name: str):
        self.name = name
        self.is_trained = False
        self.feature_columns: list = []
        self.scaler = None
        self.model = None
        self.model_path = os.path.join(settings.ml.models_dir, f"{name}.pkl")

    @abstractmethod
    def prepare_features(self, df: pd.DataFrame) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Extract feature matrix X (and optionally labels y) from OHLCV+indicator df.
        Returns (X, y) where y may be None during inference.
        """
        ...

    @abstractmethod
    def train(self, df: pd.DataFrame) -> Dict:
        """Train on historical OHLCV data. Returns metrics dict."""
        ...

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> ModelSignal:
        """Generate a signal from recent bars."""
        ...

    def save(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "scaler": self.scaler,
                "feature_columns": self.feature_columns,
                "is_trained": self.is_trained,
            }, f)
        logger.info(f"Model saved: {self.model_path}")

    def load(self) -> bool:
        if not os.path.exists(self.model_path):
            return False
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self.feature_columns = data["feature_columns"]
            self.is_trained = data["is_trained"]
            logger.info(f"Model loaded: {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Model load error: {e}")
            return False

    def _make_labels(
        self,
        close: pd.Series,
        horizon: int,
        threshold: float = 0.002,
    ) -> np.ndarray:
        """
        Create classification labels:
        1 = price goes up > threshold in `horizon` bars
        -1 = price goes down > threshold
        0 = neutral
        """
        future_ret = close.pct_change(horizon).shift(-horizon)
        labels = np.zeros(len(future_ret))
        labels[future_ret > threshold] = 1
        labels[future_ret < -threshold] = -1
        return labels
