"""
AI-powered strategy: uses the Ensemble model to generate signals.
"""

import pandas as pd
from typing import List, Optional

from strategies.base_strategy import BaseStrategy, TradeSignal
from models.ensemble_model import EnsembleModel
from indicators.technical import TechnicalIndicators
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="strategies.ai")


class AIStrategy(BaseStrategy):
    name = "ai_ensemble"

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1h",
        min_confidence: float = None,
    ):
        super().__init__(symbols, timeframe)
        self.min_confidence = min_confidence or settings.ml.min_confidence
        self.model = EnsembleModel(name="ensemble")
        self.model.load()

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        if df is None or len(df) < settings.ml.lookback_window + 50:
            return []

        signal = self.model.predict(df)

        if signal.confidence < self.min_confidence:
            return []

        if signal.direction == "neutral":
            return []

        price = float(df["close"].iloc[-1])
        atr = TechnicalIndicators.atr(df["high"], df["low"], df["close"], 14).iloc[-1]
        atr = float(atr) if not pd.isna(atr) else price * 0.01

        if signal.direction == "buy":
            stop_loss = price - 2.0 * atr
            take_profit = price + 3.0 * atr
        else:
            stop_loss = price + 2.0 * atr
            take_profit = price - 3.0 * atr

        return [TradeSignal(
            symbol=symbol,
            direction=signal.direction,
            confidence=signal.confidence,
            strategy_name=self.name,
            price=price,
            stop_loss=round(stop_loss, 5),
            take_profit=round(take_profit, 5),
            timeframe=self.timeframe,
            metadata=signal.metadata,
        )]
