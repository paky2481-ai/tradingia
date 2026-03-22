"""
[Paky] IG Markets Broker — REST API v2

Documentazione ufficiale: https://labs.ig.com/rest-trading-api-reference

Funzionalità implementate:
  - Autenticazione (CST + X-SECURITY-TOKEN, refresh automatico)
  - Account info: balance, deposit, margin usato, free margin
  - Posizioni aperte (OTC/CFD): lista, apertura, chiusura
  - Storico trade
  - Prezzi live via REST polling
  - Demo e Live supportati

Strumenti supportati (epic IG → simbolo interno):
  EUR/USD, GBP/USD, EUR/GBP, USD/JPY, XAU/USD,
  S&P 500 (US 500), DAX 40 (Germany 40)

Credenziali richieste nel .env:
  IG_API_KEY=...
  IG_USERNAME=...
  IG_PASSWORD=...
  IG_ACCOUNT_TYPE=demo  # o live
  IG_ACCOUNT_ID=...     # opzionale, usa il default account

NOTE su dimensioni lotti IG:
  - Forex CFD: 1 lotto = 100.000 unità valuta base
  - Gold CFD: dimensione contratto = 100 oz
  - Indici: dimensione contratto = 1 punto
  - Il parametro 'quantity' nel broker è in LOTTI (es. 0.01 = micro lotto)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

from brokers.base_broker import BaseBroker, OrderResult, AccountInfo
from utils.logger import get_logger

logger = get_logger.bind(name="brokers.ig")

# ─── Epic mapping: simbolo interno → epic IG ─────────────────────────────────
# Gli epic sono i codici prodotto di IG per i CFD
EPIC_MAP: Dict[str, str] = {
    "EURUSD=X":  "CS.D.EURUSD.CFD.IP",
    "GBPUSD=X":  "CS.D.GBPUSD.CFD.IP",
    "EURGBP=X":  "CS.D.EURGBP.CFD.IP",
    "JPY=X":     "CS.D.USDJPY.CFD.IP",
    "XAUUSD=X":  "CS.D.CFEGOLD.CFE.IP",
    "^GSPC":     "IX.D.SPTRD.CFD.IP",      # US 500
    "^GDAXI":    "IX.D.DAX.CFD.IP",         # Germany 40
    "^FTSE":     "IX.D.FTSE.CFD.IP",        # UK 100
}

# Dimensione lotto in unità per ogni strumento
# Usato per convertire "lotti" → unità per IG
LOT_SIZE: Dict[str, float] = {
    "EURUSD=X": 100_000,
    "GBPUSD=X": 100_000,
    "EURGBP=X": 100_000,
    "JPY=X":    100_000,
    "XAUUSD=X": 100,       # 1 lotto = 100 oz
    "^GSPC":    1.0,        # indice: contratti
    "^GDAXI":   1.0,
    "^FTSE":    1.0,
}


class IGBroker(BaseBroker):
    """
    IG Markets REST API broker.
    Paper trading: usa IG Demo Account (https://demo-api.ig.com)
    Live trading: usa IG Live Account (https://api.ig.com)
    """

    name = "ig"

    # IG REST API base URLs
    _BASE_DEMO = "https://demo-api.ig.com/gateway/deal"
    _BASE_LIVE = "https://api.ig.com/gateway/deal"

    def __init__(
        self,
        api_key: str = "",
        username: str = "",
        password: str = "",
        account_type: str = "demo",   # "demo" o "live"
        account_id: str = "",
    ):
        # Se non passate esplicitamente, cerca nel .env
        import os
        self._api_key    = api_key    or os.getenv("IG_API_KEY", "")
        self._username   = username   or os.getenv("IG_USERNAME", "")
        self._password   = password   or os.getenv("IG_PASSWORD", "")
        self._acct_type  = (account_type or os.getenv("IG_ACCOUNT_TYPE", "demo")).lower()
        self._account_id = account_id or os.getenv("IG_ACCOUNT_ID", "")

        self._base_url   = self._BASE_LIVE if self._acct_type == "live" else self._BASE_DEMO
        self._cst: Optional[str]            = None
        self._security_token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False

    # ─────────────────────────────────────────────────────────────────────
    # Connessione e autenticazione
    # ─────────────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Autentica e ottiene CST + X-SECURITY-TOKEN."""
        if not self._api_key or not self._username or not self._password:
            logger.warning(
                "IG: credenziali mancanti. Imposta IG_API_KEY, IG_USERNAME, IG_PASSWORD nel .env"
            )
            return False

        try:
            self._session = aiohttp.ClientSession()
            headers = {
                "Content-Type": "application/json; charset=UTF-8",
                "Accept": "application/json; charset=UTF-8",
                "X-IG-API-KEY": self._api_key,
                "Version": "2",
            }
            body = {
                "identifier": self._username,
                "password": self._password,
            }
            if self._account_id:
                body["encryptedPassword"] = False

            async with self._session.post(
                f"{self._base_url}/session", json=body, headers=headers
            ) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    logger.error(f"IG auth error {resp.status}: {text}")
                    return False

                self._cst            = resp.headers.get("CST")
                self._security_token = resp.headers.get("X-SECURITY-TOKEN")
                data = await resp.json()

                # Se non specificato, usa l'account di default
                if not self._account_id:
                    self._account_id = data.get("currentAccountId", "")

                self._connected = True
                mode = "DEMO" if self._acct_type == "demo" else "LIVE"
                logger.info(
                    f"IG [{mode}] connesso | account={self._account_id}"
                )
                return True

        except Exception as e:
            logger.error(f"IG connect error: {e}")
            return False

    async def _ensure_connected(self):
        """Riconnette se il token è scaduto (IG: sessione dura 6h)."""
        if not self._connected or not self._cst:
            await self.connect()

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json; charset=UTF-8",
            "X-IG-API-KEY": self._api_key,
            "CST": self._cst or "",
            "X-SECURITY-TOKEN": self._security_token or "",
            "Version": "1",
        }

    async def _get(self, path: str, version: str = "1") -> Optional[dict]:
        await self._ensure_connected()
        if not self._session:
            return None
        h = {**self._headers(), "Version": version}
        try:
            async with self._session.get(f"{self._base_url}{path}", headers=h) as r:
                if r.status == 200:
                    return await r.json()
                text = await r.text()
                logger.warning(f"IG GET {path} → {r.status}: {text[:200]}")
                return None
        except Exception as e:
            logger.error(f"IG GET {path} error: {e}")
            return None

    async def _post(self, path: str, body: dict, version: str = "1") -> Optional[dict]:
        await self._ensure_connected()
        if not self._session:
            return None
        h = {**self._headers(), "Version": version}
        try:
            async with self._session.post(
                f"{self._base_url}{path}", json=body, headers=h
            ) as r:
                try:
                    data = await r.json()
                except Exception:
                    data = {"error": await r.text()}
                if r.status in (200, 201):
                    return data
                logger.warning(f"IG POST {path} → {r.status}: {data}")
                return None
        except Exception as e:
            logger.error(f"IG POST {path} error: {e}")
            return None

    async def _delete(self, path: str, body: dict = None, version: str = "1") -> Optional[dict]:
        await self._ensure_connected()
        h = {**self._headers(), "Version": version, "_method": "DELETE"}
        async with self._session.post(
            f"{self._base_url}{path}", json=body or {}, headers=h
        ) as r:
            if r.status in (200, 204):
                return await r.json() if r.content_length else {}
            text = await r.text()
            logger.warning(f"IG DELETE {path} → {r.status}: {text[:200]}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # Account info completo
    # ─────────────────────────────────────────────────────────────────────

    async def get_account(self) -> Optional[AccountInfo]:
        data = await self._get(f"/accounts/{self._account_id}", version="1")
        if data is None:
            # fallback: lista accounts
            accts = await self._get("/accounts")
            if accts:
                for a in accts.get("accounts", []):
                    if a.get("accountId") == self._account_id or not self._account_id:
                        data = a
                        break

        if not data:
            return AccountInfo(equity=0, cash=0, buying_power=0, broker="ig")

        balance    = data.get("balance", {})
        equity     = float(balance.get("balance", 0))
        deposit    = float(balance.get("deposit", 0))
        profit_loss= float(balance.get("profitLoss", 0))
        available  = float(balance.get("available", 0))
        currency   = data.get("currency", "GBP")

        return AccountInfo(
            equity=equity + profit_loss,
            cash=available,
            buying_power=available,
            currency=currency,
            broker="ig",
        )

    async def get_account_details(self) -> dict:
        """
        Ritorna dettagli completi del conto IG:
        balance, deposit, profitLoss, available, margin, currency.
        Usato dal PortfolioPanel della GUI.
        """
        data = await self._get(f"/accounts/{self._account_id}")
        if not data:
            accts = await self._get("/accounts")
            if accts:
                for a in accts.get("accounts", []):
                    if a.get("accountId") == self._account_id:
                        data = a
                        break

        if not data:
            return {}

        balance = data.get("balance", {})
        return {
            "broker":        "IG Markets",
            "account_id":    data.get("accountId", ""),
            "account_name":  data.get("accountName", ""),
            "account_type":  data.get("accountType", ""),
            "currency":      data.get("currency", "GBP"),
            "balance":       float(balance.get("balance", 0)),
            "deposit":       float(balance.get("deposit", 0)),    # deposito totale
            "profit_loss":   float(balance.get("profitLoss", 0)), # P&L non realizzato
            "available":     float(balance.get("available", 0)),  # margine libero
            "equity":        float(balance.get("balance", 0)) + float(balance.get("profitLoss", 0)),
            "margin_used":   float(balance.get("deposit", 0)),
            "margin_pct":    round(
                float(balance.get("deposit", 0)) /
                max(float(balance.get("balance", 0)) + float(balance.get("profitLoss", 0)), 1) * 100,
                2
            ),
            "preferred":     data.get("preferred", False),
            "status":        data.get("status", ""),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Posizioni aperte
    # ─────────────────────────────────────────────────────────────────────

    async def get_positions(self) -> List[Dict]:
        data = await self._get("/positions/otc")
        if not data:
            return []

        result = []
        for item in data.get("positions", []):
            pos    = item.get("position", {})
            market = item.get("market", {})
            epic   = market.get("epic", "")

            # Converti epic → simbolo interno
            symbol = self._epic_to_symbol(epic)

            entry_lvl = float(pos.get("openLevel", 0))
            bid       = float(market.get("bid", entry_lvl))
            offer     = float(market.get("offer", entry_lvl))
            direction = pos.get("direction", "BUY").lower()
            size      = float(pos.get("size", 0))
            current   = bid if direction == "buy" else offer

            pnl = (current - entry_lvl) * size if direction == "buy" \
                  else (entry_lvl - current) * size

            result.append({
                "symbol":             symbol,
                "epic":               epic,
                "deal_id":            pos.get("dealId", ""),
                "direction":          direction,
                "quantity":           size,
                "avg_entry_price":    entry_lvl,
                "current_price":      current,
                "unrealized_pnl":     round(pnl, 2),
                "unrealized_pnl_pct": round(pnl / max(entry_lvl * size, 1e-8) * 100, 3),
                "market_value":       round(current * size, 2),
                "deal_size":          pos.get("size", 0),
                "currency":           pos.get("currency", ""),
                "created_date":       pos.get("createdDateUTC", ""),
                "limit_level":        pos.get("limitLevel"),   # TP
                "stop_level":         pos.get("stopLevel"),    # SL
                "status":             market.get("marketStatus", ""),
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
        epic = EPIC_MAP.get(symbol)
        if not epic:
            return OrderResult(
                False, None, symbol, direction, quantity, None,
                "error", f"Epic non trovato per {symbol}"
            )

        # IG usa SELL/BUY in maiuscolo
        ig_direction = "BUY" if direction.lower() == "buy" else "SELL"

        # Prezzo corrente per il fill
        price_data = await self._get_price(epic)
        if order_type == "market":
            fill_price = (price_data.get("offer") if ig_direction == "BUY"
                         else price_data.get("bid", 0))
        else:
            fill_price = limit_price or price_data.get("offer", 0)

        body = {
            "epic":           epic,
            "expiry":         "-",
            "direction":      ig_direction,
            "size":           str(quantity),
            "orderType":      "MARKET" if order_type == "market" else "LIMIT",
            "timeInForce":    "FILL_OR_KILL",
            "guaranteedStop": False,
            "forceOpen":      True,
            "currencyCode":   "GBP",
        }

        if order_type == "limit" and limit_price:
            body["level"] = str(limit_price)

        if stop_price:
            body["stopLevel"] = str(stop_price)

        if limit_price and order_type == "market":
            body["limitLevel"] = str(limit_price)

        resp = await self._post("/positions/otc", body, version="2")

        if resp and resp.get("dealStatus") == "ACCEPTED":
            deal_id = resp.get("dealId", resp.get("dealReference", ""))
            logger.info(
                f"IG ORDER ACCEPTED | {ig_direction} {quantity} {symbol} | deal={deal_id}"
            )
            return OrderResult(
                success=True, order_id=deal_id, symbol=symbol,
                direction=direction, quantity=quantity,
                price=fill_price, status="filled",
            )

        reason = resp.get("reason", "unknown") if resp else "no response"
        logger.warning(f"IG ORDER REJECTED | {symbol} {direction} | reason={reason}")
        return OrderResult(
            False, None, symbol, direction, quantity, None, "rejected", reason
        )

    # ─────────────────────────────────────────────────────────────────────
    # Chiusura posizione specifica
    # ─────────────────────────────────────────────────────────────────────

    async def close_position_by_deal(self, deal_id: str, size: float, direction: str) -> bool:
        """Chiudi una posizione tramite deal_id."""
        close_dir = "SELL" if direction.lower() == "buy" else "BUY"
        body = {
            "dealId":      deal_id,
            "direction":   close_dir,
            "size":        str(size),
            "orderType":   "MARKET",
            "timeInForce": "FILL_OR_KILL",
        }
        resp = await self._delete("/positions/otc", body, version="1")
        if resp and resp.get("dealStatus") == "ACCEPTED":
            logger.info(f"IG CLOSE ACCEPTED | deal={deal_id}")
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Prezzi live
    # ─────────────────────────────────────────────────────────────────────

    async def _get_price(self, epic: str) -> dict:
        data = await self._get(f"/markets/{epic}")
        if not data:
            return {"bid": 0, "offer": 0}
        snap = data.get("snapshot", {})
        return {
            "bid":   float(snap.get("bid", 0)),
            "offer": float(snap.get("offer", 0)),
            "high":  float(snap.get("high", 0)),
            "low":   float(snap.get("low", 0)),
        }

    async def get_price(self, symbol: str) -> Optional[float]:
        """Restituisce il prezzo mid per un simbolo."""
        epic = EPIC_MAP.get(symbol)
        if not epic:
            return None
        p = await self._get_price(epic)
        if p["bid"] and p["offer"]:
            return (p["bid"] + p["offer"]) / 2
        return None

    # ─────────────────────────────────────────────────────────────────────
    # Storico trade
    # ─────────────────────────────────────────────────────────────────────

    async def get_trade_history(self, max_span_seconds: int = 86400) -> List[Dict]:
        """Ultime 24h di trade chiusi."""
        data = await self._get("/history/activity", version="3")
        if not data:
            return []

        result = []
        for act in data.get("activities", []):
            if act.get("type") not in ("POSITION", "TRADE"):
                continue
            details = act.get("details", {})
            result.append({
                "date":      act.get("date", ""),
                "epic":      details.get("epic", ""),
                "symbol":    self._epic_to_symbol(details.get("epic", "")),
                "direction": details.get("direction", "").lower(),
                "size":      details.get("size", 0),
                "price":     details.get("level", 0),
                "pnl":       details.get("profitAndLoss", 0),
                "action":    act.get("action", ""),
                "deal_id":   act.get("dealId", ""),
            })
        return result

    # ─────────────────────────────────────────────────────────────────────
    # Ordini pending
    # ─────────────────────────────────────────────────────────────────────

    async def get_orders(self) -> List[Dict]:
        data = await self._get("/workingorders/otc")
        if not data:
            return []
        orders = []
        for o in data.get("workingOrders", []):
            wo = o.get("workingOrderData", {})
            orders.append({
                "deal_id":    wo.get("dealId", ""),
                "epic":       wo.get("epic", ""),
                "direction":  wo.get("direction", "").lower(),
                "size":       wo.get("size", 0),
                "order_type": wo.get("orderType", ""),
                "level":      wo.get("level", 0),
            })
        return orders

    async def cancel_order(self, order_id: str) -> bool:
        resp = await self._delete(f"/workingorders/otc/{order_id}")
        return resp is not None

    # ─────────────────────────────────────────────────────────────────────
    # Utilità
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _epic_to_symbol(epic: str) -> str:
        """Converte epic IG → simbolo interno."""
        for sym, ep in EPIC_MAP.items():
            if ep == epic:
                return sym
        return epic

    async def disconnect(self):
        if self._session:
            try:
                await self._session.delete(
                    f"{self._base_url}/session", headers=self._headers()
                )
            except Exception:
                pass
            await self._session.close()
        self._connected = False
