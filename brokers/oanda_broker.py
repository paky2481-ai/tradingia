"""
[Paky] OANDA Broker — REST API v20

Documentazione: https://developer.oanda.com/rest-live-v20/introduction/

Funzionalità:
  - Account completo: balance, NAV, margin usato/disponibile, P&L
  - Posizioni live con P&L non realizzato in tempo reale
  - Ordini market/limit/stop
  - Storico trade
  - Prezzi streaming (polling) via /pricing/stream o REST polling

Strumenti supportati: forex e XAU/USD (OANDA non ha indici azionari nativi)
Per indici: usa IG o paper broker.

Credenziali richieste nel .env:
  OANDA_API_TOKEN=...
  OANDA_ACCOUNT_ID=...
  OANDA_ENVIRONMENT=practice  # practice (demo) o live

OANDA instrument format: EUR_USD, GBP_USD, XAU_USD, ecc.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

from brokers.base_broker import BaseBroker, OrderResult, AccountInfo
from utils.logger import get_logger

logger = get_logger.bind(name="brokers.oanda")

# Mapping simbolo interno → strumento OANDA
OANDA_INSTRUMENT_MAP: Dict[str, str] = {
    "EURUSD=X": "EUR_USD",
    "GBPUSD=X": "GBP_USD",
    "EURGBP=X": "EUR_GBP",
    "JPY=X":    "USD_JPY",
    "XAUUSD=X": "XAU_USD",
    "AUDUSD=X": "AUD_USD",
    "USDCHF=X": "USD_CHF",
    "USDCAD=X": "USD_CAD",
}

# OANDA URL base per environment
OANDA_URLS = {
    "practice": "https://api-fxpractice.oanda.com/v3",
    "live":     "https://api-fxtrade.oanda.com/v3",
}


class OANDABroker(BaseBroker):
    """
    OANDA REST API v20 broker.
    Practice (demo): gratuito, nessun deposito richiesto.
    Live: richiede un conto reale OANDA (min. $100 USD).
    """

    name = "oanda"

    def __init__(
        self,
        api_token: str = "",
        account_id: str = "",
        environment: str = "practice",
    ):
        self._token    = api_token    or os.getenv("OANDA_API_TOKEN", "")
        self._acct_id  = account_id   or os.getenv("OANDA_ACCOUNT_ID", "")
        self._env      = (environment or os.getenv("OANDA_ENVIRONMENT", "practice")).lower()
        self._base_url = OANDA_URLS.get(self._env, OANDA_URLS["practice"])
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False

    # ─────────────────────────────────────────────────────────────────────
    # Connessione
    # ─────────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        if not self._token or not self._acct_id:
            logger.warning(
                "OANDA: credenziali mancanti. Imposta OANDA_API_TOKEN e OANDA_ACCOUNT_ID nel .env"
            )
            return False

        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type":  "application/json",
            }
        )

        # Test connessione
        try:
            data = await self._get(f"/accounts/{self._acct_id}/summary")
            if data:
                acct = data.get("account", {})
                currency = acct.get("currency", "USD")
                nav      = acct.get("NAV", 0)
                env_label = "PRACTICE" if self._env == "practice" else "LIVE"
                logger.info(
                    f"OANDA [{env_label}] connesso | account={self._acct_id} | "
                    f"NAV={currency} {nav}"
                )
                self._connected = True
                return True
        except Exception as e:
            logger.error(f"OANDA connect error: {e}")

        return False

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type":  "application/json",
        }

    async def _get(self, path: str) -> Optional[dict]:
        if not self._session:
            logger.error("OANDA: sessione non inizializzata, chiama connect() prima")
            return None
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url) as r:
                if r.status == 200:
                    return await r.json()
                text = await r.text()
                logger.warning(f"OANDA GET {path} → {r.status}: {text[:200]}")
                return None
        except Exception as e:
            logger.error(f"OANDA GET {path} error: {e}")
            return None

    async def _post(self, path: str, body: dict) -> Optional[dict]:
        if not self._session:
            logger.error("OANDA: sessione non inizializzata, chiama connect() prima")
            return None
        url = f"{self._base_url}{path}"
        try:
            async with self._session.post(url, json=body) as r:
                data = await r.json()
                if r.status in (200, 201):
                    return data
                logger.warning(f"OANDA POST {path} → {r.status}: {data}")
                return None
        except Exception as e:
            logger.error(f"OANDA POST {path} error: {e}")
            return None

    async def _put(self, path: str, body: dict) -> Optional[dict]:
        url = f"{self._base_url}{path}"
        async with self._session.put(url, json=body) as r:
            if r.status in (200, 201):
                return await r.json()
            return None

    # ─────────────────────────────────────────────────────────────────────
    # Account info completo
    # ─────────────────────────────────────────────────────────────────────

    async def get_account(self) -> Optional[AccountInfo]:
        data = await self._get(f"/accounts/{self._acct_id}/summary")
        if not data:
            return AccountInfo(equity=0, cash=0, buying_power=0, broker="oanda")
        a = data.get("account", {})
        return AccountInfo(
            equity=float(a.get("NAV", 0)),
            cash=float(a.get("balance", 0)),
            buying_power=float(a.get("marginAvailable", 0)),
            currency=a.get("currency", "USD"),
            broker="oanda",
        )

    async def get_account_details(self) -> dict:
        """
        Ritorna tutti i dettagli del conto OANDA per il PortfolioPanel:
        NAV, balance, P&L non realizzato, margine usato, leva usata, ecc.
        """
        data = await self._get(f"/accounts/{self._acct_id}/summary")
        if not data:
            return {}

        a = data.get("account", {})
        nav              = float(a.get("NAV", 0))
        balance          = float(a.get("balance", 0))
        unrealized_pnl   = float(a.get("unrealizedPL", 0))
        realized_pnl     = float(a.get("pl", 0))
        margin_used      = float(a.get("marginUsed", 0))
        margin_available = float(a.get("marginAvailable", 0))
        open_trade_count = int(a.get("openTradeCount", 0))
        open_pos_count   = int(a.get("openPositionCount", 0))

        margin_pct = round(margin_used / max(nav, 1) * 100, 2) if nav else 0

        return {
            "broker":           "OANDA",
            "environment":      self._env.upper(),
            "account_id":       self._acct_id,
            "currency":         a.get("currency", "USD"),
            "nav":              nav,              # Net Asset Value
            "balance":          balance,          # deposito + P&L realizzato
            "unrealized_pnl":   unrealized_pnl,  # P&L non realizzato totale
            "realized_pnl":     realized_pnl,    # P&L realizzato storico
            "equity":           nav,
            "margin_used":      margin_used,      # margine impegnato
            "margin_available": margin_available, # margine libero
            "margin_pct":       margin_pct,
            "open_trades":      open_trade_count,
            "open_positions":   open_pos_count,
            "leverage":         a.get("marginRate", ""),
            "hedging_enabled":  a.get("hedgingEnabled", False),
            "last_updated":     datetime.utcnow().isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Posizioni
    # ─────────────────────────────────────────────────────────────────────

    async def get_positions(self) -> List[Dict]:
        data = await self._get(f"/accounts/{self._acct_id}/openPositions")
        if not data:
            return []

        result = []
        for pos in data.get("positions", []):
            instrument = pos.get("instrument", "")
            symbol     = self._oanda_to_symbol(instrument)

            # OANDA separa long e short
            long  = pos.get("long", {})
            short = pos.get("short", {})

            # Determina lato dominante
            long_units  = abs(float(long.get("units", 0)))
            short_units = abs(float(short.get("units", 0)))

            if long_units > 0:
                units     = long_units
                direction = "buy"
                entry     = float(long.get("averagePrice", 0))
                pnl       = float(long.get("unrealizedPL", 0))
                trade_ids = long.get("tradeIDs", [])
            else:
                units     = short_units
                direction = "sell"
                entry     = float(short.get("averagePrice", 0))
                pnl       = float(short.get("unrealizedPL", 0))
                trade_ids = short.get("tradeIDs", [])

            pnl_pct = pnl / max(entry * units, 1e-8) * 100

            result.append({
                "symbol":          symbol,
                "instrument":      instrument,
                "direction":       direction,
                "quantity":        units,
                "avg_entry_price": entry,
                "current_price":   0,    # aggiornato in position_monitor
                "unrealized_pnl":  round(pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 3),
                "market_value":    round(entry * units, 2),
                "trade_ids":       trade_ids,
            })

        return result

    # ─────────────────────────────────────────────────────────────────────
    # Apertura ordine
    # ─────────────────────────────────────────────────────────────────────

    async def place_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> OrderResult:
        instrument = OANDA_INSTRUMENT_MAP.get(symbol)
        if not instrument:
            return OrderResult(
                False, None, symbol, direction, quantity, None,
                "error", f"Strumento non supportato da OANDA: {symbol}"
            )

        # Unità: negative per short, positive per long
        # Per JPY crosses (es. USD_JPY) OANDA usa le stesse unità della base (USD)
        units = int(quantity * 100_000)
        if direction.lower() == "sell":
            units = -abs(units)
        else:
            units = abs(units)

        if order_type == "market":
            order_body = {
                "order": {
                    "type":       "MARKET",
                    "instrument": instrument,
                    "units":      str(units),
                    "timeInForce": "FOK",
                    "positionFill": "DEFAULT",
                }
            }
            if stop_price:
                order_body["order"]["stopLossOnFill"] = {"price": f"{stop_price:.5f}"}
            if limit_price:
                order_body["order"]["takeProfitOnFill"] = {"price": f"{limit_price:.5f}"}

        else:
            order_body = {
                "order": {
                    "type":       "LIMIT",
                    "instrument": instrument,
                    "units":      str(units),
                    "price":      f"{limit_price:.5f}",
                    "timeInForce": "GTC",
                }
            }

        resp = await self._post(f"/accounts/{self._acct_id}/orders", order_body)

        if resp and "orderFillTransaction" in resp:
            fill   = resp["orderFillTransaction"]
            trade_id = fill.get("tradeOpened", {}).get("tradeID", fill.get("id", ""))
            price  = float(fill.get("price", 0))
            logger.info(
                f"OANDA ORDER FILLED | {direction.upper()} {quantity} {symbol} "
                f"@ {price:.5f} | tradeID={trade_id}"
            )
            return OrderResult(
                success=True, order_id=trade_id, symbol=symbol,
                direction=direction, quantity=quantity,
                price=price, status="filled",
            )

        if resp and "orderCreateTransaction" in resp:
            order_id = resp["orderCreateTransaction"].get("id", "")
            logger.info(f"OANDA ORDER PENDING | {symbol} | orderID={order_id}")
            return OrderResult(
                success=True, order_id=order_id, symbol=symbol,
                direction=direction, quantity=quantity,
                price=limit_price, status="pending",
            )

        reason = str(resp.get("errorCode", "unknown") if resp else "no response")
        return OrderResult(False, None, symbol, direction, quantity, None, "rejected", reason)

    # ─────────────────────────────────────────────────────────────────────
    # Chiusura trade
    # ─────────────────────────────────────────────────────────────────────

    async def close_trade(self, trade_id: str) -> bool:
        resp = await self._put(
            f"/accounts/{self._acct_id}/trades/{trade_id}/close", {}
        )
        if resp and "orderFillTransaction" in resp:
            pnl = resp["orderFillTransaction"].get("pl", 0)
            logger.info(f"OANDA CLOSE trade={trade_id} | P&L={pnl}")
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Prezzi
    # ─────────────────────────────────────────────────────────────────────

    async def get_price(self, symbol: str) -> Optional[float]:
        instrument = OANDA_INSTRUMENT_MAP.get(symbol)
        if not instrument:
            return None
        data = await self._get(
            f"/accounts/{self._acct_id}/pricing?instruments={instrument}"
        )
        if data and data.get("prices"):
            p = data["prices"][0]
            bid   = float(p.get("bids", [{}])[0].get("price", 0))
            offer = float(p.get("asks", [{}])[0].get("price", 0))
            return (bid + offer) / 2 if bid and offer else 0
        return None

    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Recupera prezzi per più strumenti in una sola chiamata."""
        instruments = [OANDA_INSTRUMENT_MAP[s] for s in symbols if s in OANDA_INSTRUMENT_MAP]
        if not instruments:
            return {}
        query = ",".join(instruments)
        data = await self._get(
            f"/accounts/{self._acct_id}/pricing?instruments={query}"
        )
        result = {}
        if data:
            sym_map = {v: k for k, v in OANDA_INSTRUMENT_MAP.items()}
            for p in data.get("prices", []):
                inst = p.get("instrument", "")
                sym  = sym_map.get(inst, inst)
                bid  = float(p.get("bids", [{}])[0].get("price", 0))
                ask  = float(p.get("asks", [{}])[0].get("price", 0))
                if bid and ask:
                    result[sym] = (bid + ask) / 2
        return result

    # ─────────────────────────────────────────────────────────────────────
    # Storico trade
    # ─────────────────────────────────────────────────────────────────────

    async def get_trade_history(self, count: int = 50) -> List[Dict]:
        data = await self._get(
            f"/accounts/{self._acct_id}/trades?state=CLOSED&count={count}"
        )
        if not data:
            return []

        result = []
        for trade in data.get("trades", []):
            instrument = trade.get("instrument", "")
            symbol     = self._oanda_to_symbol(instrument)
            units      = float(trade.get("initialUnits", 0))
            direction  = "buy" if units > 0 else "sell"
            result.append({
                "trade_id":     trade.get("id", ""),
                "symbol":       symbol,
                "instrument":   instrument,
                "direction":    direction,
                "quantity":     abs(units),
                "entry_price":  float(trade.get("price", 0)),
                "close_price":  float(trade.get("averageClosePrice", 0)),
                "pnl":          float(trade.get("realizedPL", 0)),
                "open_time":    trade.get("openTime", ""),
                "close_time":   trade.get("closeTime", ""),
                "duration_s":   trade.get("closeTime", ""),
            })
        return result

    async def get_orders(self) -> List[Dict]:
        data = await self._get(f"/accounts/{self._acct_id}/pendingOrders")
        if not data:
            return []
        orders = []
        for o in data.get("orders", []):
            orders.append({
                "order_id":   o.get("id", ""),
                "instrument": o.get("instrument", ""),
                "symbol":     self._oanda_to_symbol(o.get("instrument", "")),
                "direction":  "buy" if float(o.get("units", 0)) > 0 else "sell",
                "quantity":   abs(float(o.get("units", 0))),
                "type":       o.get("type", ""),
                "price":      float(o.get("price", 0)),
            })
        return orders

    async def cancel_order(self, order_id: str) -> bool:
        async with self._session.delete(
            f"{self._base_url}/accounts/{self._acct_id}/orders/{order_id}"
        ) as r:
            return r.status in (200, 204)

    # ─────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _oanda_to_symbol(instrument: str) -> str:
        for sym, inst in OANDA_INSTRUMENT_MAP.items():
            if inst == instrument:
                return sym
        return instrument

    async def disconnect(self):
        if self._session:
            await self._session.close()
        self._connected = False
