"""
Random Forest Classifier for trading signals.
Fast, interpretable, good baseline.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score

from models.base_model import BaseModel, ModelSignal
from indicators.technical import TechnicalIndicators
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="models.rf")

FEATURE_COLS = [
    "rsi_14", "rsi_7", "macd", "macd_signal", "macd_hist",
    "stoch_k", "stoch_d", "cci_20", "williams_r", "roc_12", "mfi_14",
    "bb_pct", "bb_width", "atr_14", "hist_vol_20",
    "obv", "cmf_20", "volume_ratio",
    "above_sma50", "above_sma200", "momentum_10",
    "returns", "hl_ratio", "oc_ratio",
    "ema_9", "ema_21",
]


class RandomForestModel(BaseModel):
    """Gradient-Boosted Random Forest for directional classification."""

    def __init__(self, n_estimators: int = 200, name: str = "random_forest"):
        super().__init__(name)
        self.n_estimators = n_estimators
        self.feature_importance_: Optional[pd.Series] = None

    def prepare_features(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        df_feat = TechnicalIndicators.compute_all(df)
        cols = [c for c in FEATURE_COLS if c in df_feat.columns]
        self.feature_columns = cols

        X = df_feat[cols].values
        labels = self._make_labels(
            df_feat["close"],
            horizon=settings.ml.prediction_horizon,
        )
        return X, labels

    def train(self, df: pd.DataFrame) -> Dict:
        logger.info(f"Training {self.name}...")
        X, y = self.prepare_features(df)

        # Remove NaN rows
        mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X, y = X[mask], y[mask]

        if len(X) < 100:
            logger.warning("Not enough data to train RF model")
            return {"error": "insufficient_data"}

        split = int(len(X) * settings.ml.train_test_split)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)

        self.model = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            random_state=42,
        )
        self.model.fit(X_train, y_train)

        y_pred = self.model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

        self.feature_importance_ = pd.Series(
            self.model.feature_importances_,
            index=self.feature_columns,
        ).sort_values(ascending=False)

        self.is_trained = True
        self.save()

        metrics = {
            "accuracy": acc,
            "n_samples_train": len(X_train),
            "n_samples_test": len(X_test),
            "report": report,
        }
        logger.info(f"{self.name} trained: accuracy={acc:.3f}")
        return metrics

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        if not self.is_trained:
            loaded = self.load()
            if not loaded:
                return ModelSignal("neutral", 0.0)

        df_feat = TechnicalIndicators.compute_all(df)
        X = df_feat[self.feature_columns].values[-1:]  # last bar

        if np.isnan(X).any():
            return ModelSignal("neutral", 0.0)

        X_scaled = self.scaler.transform(X)
        proba = self.model.predict_proba(X_scaled)[0]
        classes = self.model.classes_

        class_map = {-1: "sell", 0: "neutral", 1: "buy"}
        best_idx = np.argmax(proba)
        best_class = int(classes[best_idx])
        confidence = float(proba[best_idx])
        direction = class_map.get(best_class, "neutral")

        return ModelSignal(
            direction=direction,
            confidence=confidence,
            metadata={
                "probas": dict(zip([class_map.get(int(c)) for c in classes], proba.tolist())),
                "top_features": self.feature_importance_.head(5).to_dict() if self.feature_importance_ is not None else {},
            },
        )
