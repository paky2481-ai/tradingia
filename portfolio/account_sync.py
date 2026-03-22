"""
[Paky] Account Sync — Sincronizzazione portafoglio con broker reale

Sincronizza ogni 30s:
  - Balance e margine dal broker (IG o OANDA)
  - Posizioni aperte (P&L live, entry, SL/TP)
  - Trade history recenti
  - Emette eventi al SignalBus per aggiornare la GUI

Il PortfolioManager locale viene tenuto in sync con i dati reali del broker,
così la GUI mostra sempre dati accurati indipendentemente da dove è stato
aperto il trade (app, app mobile IG, web IG, ecc.)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional, Dict, List

from core.signal_bus import get_bus, EngineStatusEvent, PositionUpdateEvent
from portfolio.portfolio_manager import PortfolioManager
from utils.logger import get_logger

logger = get_logger.bind(name="account_sync")


class AccountSync:
    """
    Sincronizza il PortfolioManager locale con un broker reale.

    Supporta IG e OANDA. Si adatta automaticamente in base al tipo di broker.
    """

    SYNC_INTERVAL = 30   # secondi

    def __init__(self, broker, portfolio: PortfolioManager):
        self.broker    = broker
        self.portfolio = portfolio
        self.bus       = get_bus()
        self._running  = False
        self._broker_type = getattr(broker, "name", "unknown")

    async def start(self):
        """Avvia il loop di sincronizzazione."""
        logger.info(f"AccountSync avviato | broker={self._broker_type}")
        self._running = True

        # Prima sync immediata
        await self._sync()

        while self._running:
            await asyncio.sleep(self.SYNC_INTERVAL)
            await self._sync()

    def stop(self):
        self._running = False

    # ─────────────────────────────────────────────────────────────────────
    # Sync principale
    # ─────────────────────────────────────────────────────────────────────

    async def _sync(self):
        try:
            await asyncio.gather(
                self._sync_account(),
                self._sync_positions(),
            )
        except Exception as e:
            logger.error(f"AccountSync error: {e}")

    async def _sync_account(self):
        """Aggiorna balance, margine e equity dal broker."""
        # Usa get_account_details se disponibile (IG/OANDA extended info)
        if hasattr(self.broker, "get_account_details"):
            details = await self.broker.get_account_details()
            if not details:
                return

            equity        = details.get("equity", details.get("nav", 0))
            margin_used   = details.get("margin_used", details.get("deposit", 0))
            margin_free   = details.get("margin_available", details.get("available", 0))
            unrealized_pnl= details.get("unrealized_pnl", details.get("profit_loss", 0))
            currency      = details.get("currency", "USD")

            # Aggiorna il PortfolioManager
            self.portfolio.cash = margin_free

            # Emetti status all'engine per la GUI
            self.bus.emit_engine_status(EngineStatusEvent(
                running=True,
                mode=self._broker_type,
                equity=equity,
                daily_pnl=self.portfolio.daily_pnl,
                drawdown_pct=self.portfolio.drawdown_pct,
                open_positions=len(self.portfolio.positions),
                total_return_pct=(
                    (equity - self.portfolio.initial_capital)
                    / max(self.portfolio.initial_capital, 1) * 100
                ),
                last_scan=datetime.utcnow().strftime("%H:%M:%S"),
            ))

            self.bus.emit_log(
                f"[sync] equity={currency} {equity:,.2f} | "
                f"margine={margin_used:,.2f} | libero={margin_free:,.2f} | "
                f"P&L non realizzato={unrealized_pnl:+.2f}",
                "#484f58",
            )

        else:
            # Fallback: usa get_account base
            account = await self.broker.get_account()
            if account:
                self.portfolio.cash = account.cash

    async def _sync_positions(self):
        """Sincronizza le posizioni aperte dal broker."""
        try:
            broker_positions = await self.broker.get_positions()
        except Exception:
            return

        # Aggiorna ogni posizione nel portfolio manager
        for bp in broker_positions:
            symbol    = bp.get("symbol", "")
            direction = bp.get("direction", "buy")
            quantity  = bp.get("quantity", 0)
            entry     = bp.get("avg_entry_price", 0)
            current   = bp.get("current_price", entry)
            pnl       = bp.get("unrealized_pnl", 0)
            pnl_pct   = bp.get("unrealized_pnl_pct", 0)

            # Aggiorna prezzo nel portfolio locale
            if symbol in self.portfolio.positions:
                self.portfolio.positions[symbol].current_price = current or entry
            else:
                # Posizione aperta esternamente (es. dall'app mobile IG)
                # Aggiungila al portfolio locale
                self.portfolio.positions[symbol] = _external_position(bp)
                self.bus.emit_log(
                    f"[sync] Posizione esterna rilevata: {symbol} {direction.upper()} {quantity}",
                    "#e3b341",
                )

            # Emetti update alla GUI
            self.bus.emit_position_update(PositionUpdateEvent(
                symbol=symbol,
                display=self._get_display(symbol),
                direction=direction,
                quantity=quantity,
                entry_price=entry,
                current_price=current or entry,
                unrealized_pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 3),
                stop_loss=bp.get("stop_level") or bp.get("stopLevel") or 0,
                take_profit=bp.get("limit_level") or bp.get("limitLevel") or 0,
            ))

        # Rimuovi posizioni chiuse esternamente
        broker_symbols = {bp.get("symbol") for bp in broker_positions}
        for sym in list(self.portfolio.positions.keys()):
            if sym not in broker_symbols:
                self.portfolio.positions.pop(sym, None)
                self.bus.emit_log(
                    f"[sync] Posizione rimossa (chiusa esternamente): {sym}", "#e3b341"
                )

    # ─────────────────────────────────────────────────────────────────────
    # Full portfolio snapshot (usato dalla GUI al click "Aggiorna")
    # ─────────────────────────────────────────────────────────────────────

    async def get_full_snapshot(self) -> dict:
        """
        Snapshot completo del portafoglio per la GUI.
        Include: account details, posizioni, trade history.
        """
        account_details = {}
        positions       = []
        trade_history   = []

        if hasattr(self.broker, "get_account_details"):
            account_details = await self.broker.get_account_details() or {}

        try:
            positions = await self.broker.get_positions() or []
        except Exception:
            pass

        if hasattr(self.broker, "get_trade_history"):
            try:
                trade_history = await self.broker.get_trade_history(count=50) or []
            except Exception:
                pass

        local = self.portfolio.full_report()

        return {
            "broker":         account_details,
            "positions":      positions,
            "trade_history":  trade_history,
            "local_stats":    local,
            "snapshot_time":  datetime.utcnow().isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _get_display(symbol: str) -> str:
        _map = {
            "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
            "EURGBP=X": "EUR/GBP", "JPY=X":    "USD/JPY",
            "XAUUSD=X": "XAU/USD", "^GSPC":    "S&P 500",
            "^GDAXI":   "DAX 40",
        }
        return _map.get(symbol, symbol)


# ─────────────────────────────────────────────────────────────────────────────
# Helper per creare posizione da dato broker
# ─────────────────────────────────────────────────────────────────────────────

def _external_position(bp: dict):
    """Crea un oggetto Position dal dato di sincronizzazione broker."""
    from portfolio.portfolio_manager import Position
    return Position(
        symbol=bp.get("symbol", ""),
        asset_type="forex",
        direction=bp.get("direction", "buy"),
        quantity=bp.get("quantity", 0),
        avg_entry_price=bp.get("avg_entry_price", 0),
        current_price=bp.get("current_price", bp.get("avg_entry_price", 0)),
        stop_loss=bp.get("stop_level") or bp.get("stopLevel"),
        take_profit=bp.get("limit_level") or bp.get("limitLevel"),
        strategy="external",
    )
