"""
CCXT Broker Integration
Supports 100+ crypto exchanges: Binance, Coinbase, Kraken, Bybit, etc.
"""

from typing import Dict, List, Optional

from brokers.base_broker import BaseBroker, OrderResult, AccountInfo
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="brokers.ccxt")


class CCXTBroker(BaseBroker):
    name = "ccxt"

    def __init__(self, exchange_id: str = None):
        self.exchange_id = exchange_id or settings.broker.ccxt_exchange
        self._exchange = None

    async def connect(self) -> bool:
        try:
            import ccxt.async_support as ccxt
            exchange_cls = getattr(ccxt, self.exchange_id)
            self._exchange = exchange_cls({
                "apiKey": settings.broker.ccxt_api_key or None,
                "secret": settings.broker.ccxt_secret or None,
                "sandbox": settings.broker.ccxt_sandbox,
                "enableRateLimit": True,
            })
            await self._exchange.load_markets()
            mode = "SANDBOX" if settings.broker.ccxt_sandbox else "LIVE"
            logger.info(f"CCXT [{self.exchange_id}] [{mode}] connected")
            return True
        except Exception as e:
            logger.error(f"CCXT connect error: {e}")
            return False

    async def get_account(self) -> Optional[AccountInfo]:
        if not self._exchange:
            return None
        try:
            balance = await self._exchange.fetch_balance()
            usdt = balance.get("USDT", {})
            total = float(usdt.get("total", 0))
            free = float(usdt.get("free", 0))
            return AccountInfo(
                equity=total,
                cash=free,
                buying_power=free,
                currency="USDT",
                broker=self.exchange_id,
            )
        except Exception as e:
            logger.error(f"CCXT get_account error: {e}")
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
        if not self._exchange:
            return OrderResult(False, None, symbol, direction, quantity, None, "error", "Not connected")

        ccxt_symbol = symbol.replace("-USD", "/USDT").replace("-USDT", "/USDT")
        side = "buy" if direction == "buy" else "sell"

        try:
            if order_type == "market":
                order = await self._exchange.create_market_order(ccxt_symbol, side, quantity)
            elif order_type == "limit" and limit_price:
                order = await self._exchange.create_limit_order(ccxt_symbol, side, quantity, limit_price)
            else:
                order = await self._exchange.create_market_order(ccxt_symbol, side, quantity)

            return OrderResult(
                success=True,
                order_id=str(order.get("id")),
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                price=order.get("average") or order.get("price"),
                status=order.get("status", "open"),
            )
        except Exception as e:
            logger.error(f"CCXT order error: {e}")
            return OrderResult(False, None, symbol, direction, quantity, None, "error", str(e))

    async def cancel_order(self, order_id: str) -> bool:
        if not self._exchange:
            return False
        try:
            await self._exchange.cancel_order(order_id)
            return True
        except Exception as e:
            logger.error(f"CCXT cancel error: {e}")
            return False

    async def get_positions(self) -> List[Dict]:
        if not self._exchange:
            return []
        try:
            if hasattr(self._exchange, "fetch_positions"):
                positions = await self._exchange.fetch_positions()
                return [
                    {
                        "symbol": p["symbol"],
                        "quantity": p["contracts"],
                        "direction": p["side"],
                        "avg_entry_price": p.get("entryPrice"),
                        "current_price": p.get("markPrice"),
                        "unrealized_pnl": p.get("unrealizedPnl", 0),
                    }
                    for p in positions if p.get("contracts", 0) != 0
                ]
            return []
        except Exception as e:
            logger.error(f"CCXT get_positions error: {e}")
            return []

    async def get_orders(self) -> List[Dict]:
        if not self._exchange:
            return []
        try:
            orders = await self._exchange.fetch_open_orders()
            return [
                {
                    "id": o["id"],
                    "symbol": o["symbol"],
                    "direction": o["side"],
                    "quantity": o["amount"],
                    "type": o["type"],
                    "status": o["status"],
                    "price": o.get("price"),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"CCXT get_orders error: {e}")
            return []

    async def close(self):
        if self._exchange:
            await self._exchange.close()
