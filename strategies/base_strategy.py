"""Base Strategy interface"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime
import pandas as pd


@dataclass
class TradeSignal:
    symbol: str
    direction: str          # "buy" | "sell" | "close"
    confidence: float       # 0.0 – 1.0
    strategy_name: str
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    quantity: Optional[float] = None
    timeframe: str = "1h"
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_actionable(self) -> bool:
        return self.direction in ("buy", "sell") and self.confidence > 0


class BaseStrategy(ABC):
    """Abstract base for all trading strategies."""

    name: str = "base"

    def __init__(self, symbols: Optional[List[str]] = None, timeframe: str = "1h"):
        self.symbols = symbols or []
        self.timeframe = timeframe
        self.active = True

    @abstractmethod
    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        """Generate signals from OHLCV data."""
        ...

    def filter_signal(self, signal: TradeSignal, min_confidence: float = 0.5) -> bool:
        return signal.is_actionable and signal.confidence >= min_confidence
