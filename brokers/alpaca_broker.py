"""
Alpaca Markets Broker Integration
Supports: stocks, ETFs, crypto (via Alpaca)
Paper trading + live trading
"""

import asyncio
from typing import Dict, List, Optional

from brokers.base_broker import BaseBroker, OrderResult, AccountInfo
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="brokers.alpaca")


class AlpacaBroker(BaseBroker):
    name = "alpaca"

    def __init__(self):
        self._api = None
        self.paper = settings.broker.alpaca_paper

    async def connect(self) -> bool:
        try:
            import alpaca_trade_api as tradeapi
            self._api = tradeapi.REST(
                key_id=settings.broker.alpaca_api_key,
                secret_key=settings.broker.alpaca_secret_key,
                base_url=settings.broker.alpaca_base_url,
            )
            account = await asyncio.to_thread(self._api.get_account)
            mode = "PAPER" if self.paper else "LIVE"
            logger.info(f"Alpaca [{mode}] connected. Equity: ${float(account.equity):,.2f}")
            return True
        except Exception as e:
            logger.error(f"Alpaca connect error: {e}")
            return False

    async def get_account(self) -> Optional[AccountInfo]:
        if not self._api:
            return None
        try:
            acc = await asyncio.to_thread(self._api.get_account)
            return AccountInfo(
                equity=float(acc.equity),
                cash=float(acc.cash),
                buying_power=float(acc.buying_power),
                broker="alpaca",
            )
        except Exception as e:
            logger.error(f"Alpaca get_account error: {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> OrderResult:
        if not self._api:
            return OrderResult(False, None, symbol, direction, quantity, None, "error", "Not connected")

        try:
            side = "buy" if direction == "buy" else "sell"
            kwargs = dict(
                symbol=symbol,
                qty=str(round(quantity, 4)),
                side=side,
                type=order_type,
                time_in_force="day",
            )
            if order_type == "limit" and limit_price:
                kwargs["limit_price"] = str(limit_price)
            if order_type in ("stop", "stop_limit") and stop_price:
                kwargs["stop_price"] = str(stop_price)

            order = await asyncio.to_thread(self._api.submit_order, **kwargs)
            logger.info(f"Alpaca order: {order.id} | {side} {quantity} {symbol}")
            return OrderResult(
                success=True,
                order_id=str(order.id),
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                price=float(order.filled_avg_price or 0) or None,
                status=str(order.status),
            )
        except Exception as e:
            logger.error(f"Alpaca order error: {e}")
            return OrderResult(False, None, symbol, direction, quantity, None, "error", str(e))

    async def cancel_order(self, order_id: str) -> bool:
        if not self._api:
            return False
        try:
            await asyncio.to_thread(self._api.cancel_order, order_id)
            return True
        except Exception as e:
            logger.error(f"Alpaca cancel error: {e}")
            return False

    async def get_positions(self) -> List[Dict]:
        if not self._api:
            return []
        try:
            positions = await asyncio.to_thread(self._api.list_positions)
            return [
                {
                    "symbol": p.symbol,
                    "quantity": float(p.qty),
                    "direction": "buy" if float(p.qty) > 0 else "sell",
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pnl": float(p.unrealized_pl),
                    "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                    "market_value": float(p.market_value),
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Alpaca get_positions error: {e}")
            return []

    async def get_orders(self) -> List[Dict]:
        if not self._api:
            return []
        try:
            orders = await asyncio.to_thread(self._api.list_orders, status="open")
            return [
                {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "direction": o.side,
                    "quantity": float(o.qty),
                    "type": o.type,
                    "status": o.status,
                    "submitted_at": str(o.submitted_at),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Alpaca get_orders error: {e}")
            return []
