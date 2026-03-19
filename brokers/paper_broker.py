"""
Paper Trading Broker (simulated, no real money)
Used for testing strategies without API keys.
"""

from typing import Dict, List, Optional
from datetime import datetime
import uuid

from brokers.base_broker import BaseBroker, OrderResult, AccountInfo
from utils.logger import get_logger

logger = get_logger.bind(name="brokers.paper")


class PaperBroker(BaseBroker):
    """Full-featured simulated broker with realistic fills."""

    name = "paper"

    def __init__(self, initial_capital: float = 100_000.0, commission_pct: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self._cash = initial_capital
        self._positions: Dict[str, Dict] = {}
        self._orders: List[Dict] = []
        self._price_feed: Dict[str, float] = {}   # updated externally

    async def connect(self) -> bool:
        logger.info(f"Paper broker connected. Capital: ${self.initial_capital:,.2f}")
        return True

    def set_price(self, symbol: str, price: float):
        """Update current market price."""
        self._price_feed[symbol] = price

    async def get_account(self) -> Optional[AccountInfo]:
        positions_value = sum(
            p["quantity"] * self._price_feed.get(p["symbol"], p["entry_price"])
            for p in self._positions.values()
        )
        equity = self._cash + positions_value
        return AccountInfo(
            equity=equity,
            cash=self._cash,
            buying_power=self._cash,
            broker="paper",
        )

    async def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> OrderResult:
        price = limit_price or self._price_feed.get(symbol, 0)
        if price == 0:
            return OrderResult(False, None, symbol, direction, quantity, None, "error", "No price available")

        commission = price * quantity * self.commission_pct
        cost = price * quantity + commission

        if direction == "buy":
            if cost > self._cash:
                return OrderResult(False, None, symbol, direction, quantity, price, "rejected", "Insufficient cash")
            self._cash -= cost
            self._positions[symbol] = {
                "symbol": symbol,
                "direction": "buy",
                "quantity": quantity,
                "entry_price": price,
                "opened_at": datetime.utcnow().isoformat(),
            }
        else:
            if symbol in self._positions:
                pos = self._positions.pop(symbol)
                proceeds = price * pos["quantity"] - commission
                self._cash += proceeds
            else:
                # Short (simplified)
                self._cash += price * quantity - commission
                self._positions[symbol] = {
                    "symbol": symbol,
                    "direction": "sell",
                    "quantity": quantity,
                    "entry_price": price,
                    "opened_at": datetime.utcnow().isoformat(),
                }

        order_id = str(uuid.uuid4())[:8]
        logger.info(
            f"PAPER ORDER | {direction.upper()} {quantity:.4f} {symbol} @ {price:.5f} "
            f"[comm: {commission:.2f}]"
        )
        return OrderResult(
            success=True,
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            price=price,
            status="filled",
        )

    async def cancel_order(self, order_id: str) -> bool:
        return True  # Paper orders fill instantly

    async def get_positions(self) -> List[Dict]:
        result = []
        for pos in self._positions.values():
            current_price = self._price_feed.get(pos["symbol"], pos["entry_price"])
            if pos["direction"] == "buy":
                pnl = (current_price - pos["entry_price"]) * pos["quantity"]
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            else:
                pnl = (pos["entry_price"] - current_price) * pos["quantity"]
                pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100

            result.append({
                "symbol": pos["symbol"],
                "quantity": pos["quantity"],
                "direction": pos["direction"],
                "avg_entry_price": pos["entry_price"],
                "current_price": current_price,
                "unrealized_pnl": pnl,
                "unrealized_pnl_pct": pnl_pct,
                "market_value": current_price * pos["quantity"],
            })
        return result

    async def get_orders(self) -> List[Dict]:
        return self._orders
