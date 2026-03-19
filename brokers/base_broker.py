"""Base Broker Interface"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str]
    symbol: str
    direction: str
    quantity: float
    price: Optional[float]
    status: str
    message: str = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class AccountInfo:
    equity: float
    cash: float
    buying_power: float
    currency: str = "USD"
    broker: str = "unknown"


class BaseBroker(ABC):
    """Abstract broker interface."""

    name: str = "base"

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def get_account(self) -> Optional[AccountInfo]: ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_positions(self) -> List[Dict]: ...

    @abstractmethod
    async def get_orders(self) -> List[Dict]: ...

    async def close_position(self, symbol: str) -> OrderResult:
        """Close full position for a symbol."""
        positions = await self.get_positions()
        for pos in positions:
            if pos.get("symbol") == symbol:
                qty = abs(float(pos.get("quantity", 0)))
                direction = "sell" if pos.get("direction", "buy") == "buy" else "buy"
                return await self.place_order(symbol, direction, qty)
        return OrderResult(False, None, symbol, "", 0, None, "not_found", "Position not found")
