"""
LSTM (Long Short-Term Memory) model for sequence-based price prediction.
Uses PyTorch for GPU/CPU flexibility.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
import os

from models.base_model import BaseModel, ModelSignal
from indicators.technical import TechnicalIndicators
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="models.lstm")

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    nn = None  # type: ignore
    DataLoader = None  # type: ignore
    TensorDataset = None  # type: ignore
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed — LSTM model disabled. Run: pip install torch")

LSTM_FEATURES = [
    "returns", "log_returns", "rsi_14", "macd_hist",
    "bb_pct", "bb_width", "atr_14", "volume_ratio",
    "stoch_k", "cci_20", "obv", "cmf_20",
    "hl_ratio", "oc_ratio", "momentum_10",
]


if TORCH_AVAILABLE:
    class LSTMNetwork(nn.Module):
        def __init__(
            self,
            input_size: int,
            hidden_size: int = 128,
            num_layers: int = 2,
            dropout: float = 0.3,
            num_classes: int = 3,
        ):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0.0,
                batch_first=True,
            )
            self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)
            self.norm = nn.LayerNorm(hidden_size)
            self.head = nn.Sequential(
                nn.Linear(hidden_size, 64),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(64, num_classes),
            )

        def forward(self, x):
            lstm_out, _ = self.lstm(x)
            attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
            out = self.norm(lstm_out + attn_out)
            last = out[:, -1, :]
            return self.head(last)
else:
    LSTMNetwork = None  # type: ignore


class LSTMModel(BaseModel):
    """LSTM + Attention model for directional classification."""

    def __init__(
        self,
        window: int = None,
        hidden_size: int = 128,
        num_layers: int = 2,
        name: str = "lstm",
    ):
        super().__init__(name)
        self.window = window or settings.ml.lookback_window
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        if TORCH_AVAILABLE:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"LSTM using device: {self.device}")
        else:
            self.device = None
        self.network = None
        self.model_path = os.path.join(settings.ml.models_dir, f"{name}.pt")

    def prepare_features(
        self, df: pd.DataFrame
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        df_feat = TechnicalIndicators.compute_all(df)
        cols = [c for c in LSTM_FEATURES if c in df_feat.columns]
        self.feature_columns = cols

        data = df_feat[cols].values.astype(np.float32)
        labels = self._make_labels(df_feat["close"], settings.ml.prediction_horizon)

        # Normalize with rolling z-score
        mean = np.nanmean(data, axis=0)
        std = np.nanstd(data, axis=0) + 1e-8
        data = (data - mean) / std
        self.scaler = {"mean": mean, "std": std}

        return data, labels

    def _make_sequences(
        self, data: np.ndarray, labels: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        X, y = [], []
        for i in range(self.window, len(data)):
            seq = data[i - self.window: i]
            if not np.isnan(seq).any():
                X.append(seq)
                y.append(labels[i])
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.int64)

    def train(self, df: pd.DataFrame, epochs: int = 30, batch_size: int = 64) -> Dict:
        if not TORCH_AVAILABLE:
            logger.warning("PyTorch not available — LSTM training skipped")
            return {"error": "torch_not_installed"}
        logger.info(f"Training {self.name}...")
        data, labels = self.prepare_features(df)

        # Map labels -1/0/1 -> 0/1/2
        label_map = {-1: 0, 0: 1, 1: 2}
        labels_mapped = np.vectorize(label_map.get)(labels.astype(int))

        X, y = self._make_sequences(data, labels_mapped)
        if len(X) < 200:
            logger.warning("Insufficient data for LSTM")
            return {"error": "insufficient_data"}

        split = int(len(X) * settings.ml.train_test_split)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

        self.network = LSTMNetwork(
            input_size=len(self.feature_columns),
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
        ).to(self.device)

        optimizer = torch.optim.Adam(self.network.parameters(), lr=1e-3, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        criterion = nn.CrossEntropyLoss()

        best_val_acc = 0.0
        for epoch in range(epochs):
            self.network.train()
            total_loss = 0.0
            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                optimizer.zero_grad()
                logits = self.network(X_batch)
                loss = criterion(logits, y_batch)
                loss.backward()
                nn.utils.clip_grad_norm_(self.network.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()
            scheduler.step()

            if (epoch + 1) % 5 == 0:
                val_acc = self._eval(X_test, y_test)
                logger.debug(f"Epoch {epoch+1}/{epochs} loss={total_loss/len(train_loader):.4f} val_acc={val_acc:.3f}")
                if val_acc > best_val_acc:
                    best_val_acc = val_acc
                    self.save()

        self.is_trained = True
        return {"best_val_accuracy": best_val_acc}

    def _eval(self, X: np.ndarray, y: np.ndarray) -> float:
        self.network.eval()
        with torch.no_grad():
            X_t = torch.from_numpy(X).to(self.device)
            logits = self.network(X_t)
            preds = logits.argmax(dim=1).cpu().numpy()
        return float((preds == y).mean())

    def predict(self, df: pd.DataFrame) -> ModelSignal:
        if not TORCH_AVAILABLE:
            return ModelSignal("neutral", 0.0)
        if self.network is None:
            if not self.load():
                return ModelSignal("neutral", 0.0)

        df_feat = TechnicalIndicators.compute_all(df)
        cols = self.feature_columns
        data = df_feat[cols].values.astype(np.float32)

        mean = self.scaler["mean"]
        std = self.scaler["std"]
        data = (data - mean) / std

        if len(data) < self.window:
            return ModelSignal("neutral", 0.0)

        seq = data[-self.window:]
        if np.isnan(seq).any():
            return ModelSignal("neutral", 0.0)

        self.network.eval()
        with torch.no_grad():
            X_t = torch.from_numpy(seq[np.newaxis]).to(self.device)
            logits = self.network(X_t)
            proba = torch.softmax(logits, dim=1).cpu().numpy()[0]

        class_map = {0: "sell", 1: "neutral", 2: "buy"}
        best_idx = int(np.argmax(proba))
        confidence = float(proba[best_idx])
        direction = class_map[best_idx]

        return ModelSignal(
            direction=direction,
            confidence=confidence,
            metadata={"probas": {"sell": float(proba[0]), "neutral": float(proba[1]), "buy": float(proba[2])}},
        )

    def save(self):
        if not TORCH_AVAILABLE:
            return
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save({
            "network_state": self.network.state_dict() if self.network else None,
            "scaler": self.scaler,
            "feature_columns": self.feature_columns,
            "is_trained": self.is_trained,
            "window": self.window,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
        }, self.model_path)

    def load(self) -> bool:
        if not TORCH_AVAILABLE or not os.path.exists(self.model_path):
            return False
        try:
            checkpoint = torch.load(self.model_path, map_location=self.device)
            self.feature_columns = checkpoint["feature_columns"]
            self.scaler = checkpoint["scaler"]
            self.window = checkpoint["window"]
            self.hidden_size = checkpoint["hidden_size"]
            self.num_layers = checkpoint["num_layers"]
            self.is_trained = checkpoint["is_trained"]

            if checkpoint["network_state"] is not None:
                self.network = LSTMNetwork(
                    input_size=len(self.feature_columns),
                    hidden_size=self.hidden_size,
                    num_layers=self.num_layers,
                ).to(self.device)
                self.network.load_state_dict(checkpoint["network_state"])
                self.network.eval()
            return True
        except Exception as e:
            logger.error(f"LSTM load error: {e}")
            return False
