"""
[Paky] TradingIA — Fully Automated Engine
Loop 24/5 completamente autonomo.

Flusso ogni ciclo:
  1. Fetch candle 4H e 1H per tutti gli strumenti
  2. Applica strategia corretta per strumento
  3. Risk Manager valuta il segnale
  4. Esegue ordine sul broker (paper o live)
  5. Controlla stop/TP delle posizioni aperte
  6. Notifica via Telegram
  7. Salva su DB
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, time as dtime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from brokers.paper_broker import PaperBroker
from notifications.notifier import notifier
from risk.risk_manager import RiskManager
from strategies.base_strategy import TradeSignal
from strategies.trend_4h import TrendStrategy4H
from strategies.range_1h import RangeStrategy1H
from utils.logger import get_logger

logger = get_logger.bind(name="engine")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAZIONE STRUMENTI
# [Chloe] Selezione finale: liquidi, spread bassi, non crypto
# ─────────────────────────────────────────────────────────────────────────────

INSTRUMENTS = {
    # symbol_yf      : (display, strategy,    asset_class,  pip_size)
    "EURUSD=X"       : ("EUR/USD", "trend_4h",  "forex",      0.00001),
    "GBPUSD=X"       : ("GBP/USD", "trend_4h",  "forex",      0.00001),
    "XAUUSD=X"       : ("XAU/USD", "trend_4h",  "commodity",  0.01),
    "^GSPC"          : ("S&P 500", "trend_4h",  "index",      0.01),
    "^GDAXI"         : ("DAX 40",  "trend_4h",  "index",      0.01),
    "EURGBP=X"       : ("EUR/GBP", "range_1h",  "forex",      0.00001),
    "JPY=X"          : ("USD/JPY", "range_1h",  "forex",      0.001),
}

# [Chloe] Sessioni operative — solo London + NY overlap (max liquidità)
# UTC: London 07:00-16:00 | NY 13:00-21:00 | Overlap 13:00-16:00
TRADING_HOURS = {
    "forex":     (dtime(7, 0), dtime(21, 0)),   # London + NY
    "commodity": (dtime(8, 0), dtime(20, 0)),
    "index":     (dtime(8, 0), dtime(21, 30)),
}

# [Chloe] Giorni da evitare: venerdì > 20:00 UTC e domenica
# (liquidità cala, spread si allargano)

SCAN_INTERVAL_4H = 60 * 60 * 4     # 4 ore in secondi
SCAN_INTERVAL_1H = 60 * 60         # 1 ora
POSITION_CHECK   = 30              # secondi tra i controlli stop/TP

STATE_FILE = Path.home() / ".tradingia_engine_state.json"


# ─────────────────────────────────────────────────────────────────────────────
class TradingEngine:
    """Motore di trading completamente automatico."""

    def __init__(
        self,
        capital: float = 1000.0,
        mode: str = "paper",            # "paper" | "live"
        broker=None,
    ):
        self.capital     = capital
        self.mode        = mode
        self.broker      = broker or PaperBroker(initial_capital=capital, commission_pct=0.0001)
        self.risk        = RiskManager()
        self.trend_strat = TrendStrategy4H()
        self.range_strat = RangeStrategy1H()

        # Stato runtime
        self._positions: Dict[str, dict] = {}   # symbol → {sl, tp, direction, qty, entry}
        self._running    = False
        self._last_scan: Dict[str, datetime] = {}
        self._daily_pnl  = 0.0
        self._start_equity = capital

    # ─────────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────────

    async def run(self):
        """Avvia il motore. Non ritorna finché non viene fermato."""
        logger.info(f"TradingIA Engine avviato | modo={self.mode} | capitale=€{self.capital:,.2f}")
        await self.broker.connect()
        await notifier.notify_alert(
            "TradingIA Avviato",
            f"Modo: {self.mode.upper()} | Capitale: €{self.capital:,.2f}\n"
            f"Strumenti: {len(INSTRUMENTS)} | Strategie: trend_4h + range_1h"
        )

        self._running = True
        self._load_state()

        # Task paralleli
        await asyncio.gather(
            self._scan_loop(),
            self._position_monitor_loop(),
            self._daily_report_loop(),
        )

    async def stop(self):
        self._running = False
        self._save_state()
        logger.info("Engine fermato.")

    # ─────────────────────────────────────────────────────────────────────
    # Loop principale: scansione strumenti
    # ─────────────────────────────────────────────────────────────────────

    async def _scan_loop(self):
        while self._running:
            now_utc = datetime.now(timezone.utc)

            for symbol, (display, strategy, asset_class, pip) in INSTRUMENTS.items():
                try:
                    # [Chloe] Controlla sessione operativa
                    if not self._in_session(now_utc, asset_class):
                        continue

                    # [Chloe] Evita fine settimana
                    if now_utc.weekday() == 4 and now_utc.hour >= 20:
                        continue   # venerdì sera
                    if now_utc.weekday() == 6:
                        continue   # domenica

                    # Intervallo di scan per strategia
                    interval = SCAN_INTERVAL_4H if strategy == "trend_4h" else SCAN_INTERVAL_1H
                    last = self._last_scan.get(symbol)
                    if last and (now_utc - last).total_seconds() < interval:
                        continue

                    self._last_scan[symbol] = now_utc

                    # Fetch dati
                    tf = "4h" if strategy == "trend_4h" else "1h"
                    df = await self._fetch_candles(symbol, tf, bars=120)
                    if df is None or len(df) < 40:
                        continue

                    # Aggiorna prezzo nel broker
                    current_price = float(df["close"].iloc[-1])
                    self.broker.set_price(symbol, current_price)

                    # Nessun segnale se posizione già aperta
                    if symbol in self._positions:
                        continue

                    # Genera segnale
                    sig = (self.trend_strat.compute(df, symbol)
                           if strategy == "trend_4h"
                           else self.range_strat.compute(df, symbol))

                    if sig.direction == "none":
                        logger.debug(f"{display}: no setup — {sig.reason}")
                        continue

                    logger.info(f"{display}: segnale {sig.direction.upper()} | conf={sig.confidence:.2f} | {sig.reason}")

                    # Risk assessment
                    trade_signal = TradeSignal(
                        symbol=symbol,
                        direction=sig.direction,
                        confidence=sig.confidence,
                        stop_loss=sig.stop_loss,
                        take_profit=sig.take_profit,
                        strategy=sig.strategy,
                    )
                    account = await self.broker.get_account()
                    self.risk.update_portfolio(
                        account.equity,
                        self._positions,
                        self._daily_pnl,
                    )
                    assessment = self.risk.evaluate(trade_signal, current_price)

                    if not assessment.approved:
                        logger.warning(f"{display}: rifiutato — {assessment.reason}")
                        continue

                    # Esecuzione ordine
                    result = await self.broker.place_order(
                        symbol=symbol,
                        direction=sig.direction,
                        quantity=assessment.quantity,
                        order_type="market",
                    )

                    if result.success:
                        self._positions[symbol] = {
                            "direction": sig.direction,
                            "quantity":  assessment.quantity,
                            "entry":     current_price,
                            "sl":        assessment.stop_loss,
                            "tp":        assessment.take_profit,
                            "strategy":  sig.strategy,
                            "opened_at": now_utc.isoformat(),
                            "display":   display,
                            "pip":       pip,
                        }
                        self._save_state()

                        # Notifica Telegram
                        risk_eur = round(assessment.max_loss_usd, 2)
                        rr = abs(sig.take_profit - current_price) / abs(current_price - sig.stop_loss) if abs(current_price - sig.stop_loss) > 1e-10 else 0
                        await notifier.notify_trade(
                            symbol=display,
                            direction=sig.direction,
                            quantity=assessment.quantity,
                            price=current_price,
                        )
                        await notifier.notify_alert(
                            f"Nuovo trade: {display}",
                            f"Strategia: {sig.strategy}\n"
                            f"Direzione: {sig.direction.upper()}\n"
                            f"Entry: {current_price:.5f}\n"
                            f"SL: {assessment.stop_loss:.5f} | TP: {assessment.take_profit:.5f}\n"
                            f"R/R: 1:{rr:.1f} | Rischio: €{risk_eur:.2f}\n"
                            f"Motivo: {sig.reason}"
                        )

                except Exception as e:
                    logger.error(f"Errore scan {symbol}: {e}")

            await asyncio.sleep(60)   # controlla ogni minuto

    # ─────────────────────────────────────────────────────────────────────
    # Monitor posizioni: controlla SL/TP ogni 30s
    # ─────────────────────────────────────────────────────────────────────

    async def _position_monitor_loop(self):
        while self._running:
            await asyncio.sleep(POSITION_CHECK)

            for symbol in list(self._positions.keys()):
                pos = self._positions[symbol]
                try:
                    df = await self._fetch_candles(symbol, "5m", bars=5)
                    if df is None:
                        continue
                    price = float(df["close"].iloc[-1])
                    self.broker.set_price(symbol, price)

                    exit_reason = self.risk.check_stops(
                        symbol=symbol,
                        direction=pos["direction"],
                        current_price=price,
                        stop_loss=pos["sl"],
                        take_profit=pos["tp"],
                    )

                    if exit_reason:
                        await self._close_position(symbol, price, exit_reason)

                except Exception as e:
                    logger.error(f"Errore monitor {symbol}: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Chiusura posizione
    # ─────────────────────────────────────────────────────────────────────

    async def _close_position(self, symbol: str, price: float, reason: str):
        pos = self._positions.pop(symbol, None)
        if not pos:
            return

        close_dir = "sell" if pos["direction"] == "buy" else "buy"
        result = await self.broker.place_order(
            symbol=symbol,
            direction=close_dir,
            quantity=pos["quantity"],
            order_type="market",
        )

        if not result.success:
            self._positions[symbol] = pos  # rimetti in lista
            return

        if pos["direction"] == "buy":
            pnl = (price - pos["entry"]) * pos["quantity"]
        else:
            pnl = (pos["entry"] - price) * pos["quantity"]

        self._daily_pnl += pnl
        emoji = "✅" if pnl > 0 else "❌"
        logger.info(f"CHIUSO {pos['display']} | {reason} | P&L: {pnl:+.2f}")

        await notifier.notify_trade(
            symbol=pos["display"],
            direction=close_dir,
            quantity=pos["quantity"],
            price=price,
            pnl=pnl,
        )
        await notifier.notify_alert(
            f"{emoji} Trade chiuso: {pos['display']}",
            f"Motivo: {reason}\n"
            f"Entry: {pos['entry']:.5f} → Exit: {price:.5f}\n"
            f"P&L: €{pnl:+.2f} | P&L giornaliero: €{self._daily_pnl:+.2f}"
        )
        self._save_state()

    # ─────────────────────────────────────────────────────────────────────
    # Report giornaliero (ogni giorno alle 22:00 UTC)
    # ─────────────────────────────────────────────────────────────────────

    async def _daily_report_loop(self):
        while self._running:
            now = datetime.now(timezone.utc)
            # Attendi le 22:00 UTC
            next_report = now.replace(hour=22, minute=0, second=0, microsecond=0)
            if now >= next_report:
                next_report = next_report.replace(day=next_report.day + 1)
            wait_s = (next_report - now).total_seconds()
            await asyncio.sleep(wait_s)

            account = await self.broker.get_account()
            equity  = account.equity
            total_return = (equity - self._start_equity) / self._start_equity * 100

            report = (
                f"📊 Report giornaliero TradingIA\n"
                f"Data: {now.strftime('%Y-%m-%d')}\n"
                f"Equity: €{equity:,.2f}\n"
                f"P&L oggi: €{self._daily_pnl:+.2f}\n"
                f"Rendimento totale: {total_return:+.2f}%\n"
                f"Posizioni aperte: {len(self._positions)}\n"
                f"Drawdown: {self.risk.drawdown_pct:.1f}%"
            )
            await notifier.notify_alert("Report Giornaliero", report)
            self._daily_pnl = 0.0   # reset daily

    # ─────────────────────────────────────────────────────────────────────
    # Data feed
    # ─────────────────────────────────────────────────────────────────────

    async def _fetch_candles(
        self, symbol: str, timeframe: str, bars: int = 120
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV da yfinance (paper) o broker API (live)."""
        try:
            import yfinance as yf
            tf_map = {"1h": "1h", "4h": "1h", "5m": "5m"}  # yf non ha 4H nativo
            period_map = {
                "5m": "5d", "1h": "60d", "4h": "60d"
            }
            interval = tf_map.get(timeframe, "1h")
            period   = period_map.get(timeframe, "60d")

            df = await asyncio.to_thread(
                lambda: yf.download(symbol, period=period, interval=interval,
                                    auto_adjust=True, progress=False)
            )
            if df is None or len(df) == 0:
                return None

            df.columns = [c.lower() if isinstance(c, str) else c[0].lower()
                          for c in df.columns]

            # Aggrega a 4H se richiesto
            if timeframe == "4h":
                df = df.resample("4H").agg({
                    "open": "first", "high": "max",
                    "low": "min",   "close": "last", "volume": "sum"
                }).dropna()

            return df.tail(bars)

        except Exception as e:
            logger.warning(f"Feed error {symbol}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # [Chloe] Controllo sessione operativa
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _in_session(now_utc: datetime, asset_class: str) -> bool:
        hours = TRADING_HOURS.get(asset_class, (dtime(0, 0), dtime(23, 59)))
        current_time = now_utc.time().replace(tzinfo=None)
        return hours[0] <= current_time <= hours[1]

    # ─────────────────────────────────────────────────────────────────────
    # Persistenza stato
    # ─────────────────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            STATE_FILE.write_text(json.dumps({
                "positions": self._positions,
                "daily_pnl": self._daily_pnl,
            }, default=str))
        except Exception:
            pass

    def _load_state(self):
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text())
                self._positions = data.get("positions", {})
                self._daily_pnl = data.get("daily_pnl", 0.0)
                if self._positions:
                    logger.info(f"Stato ripristinato: {len(self._positions)} posizioni aperte")
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Status (per GUI)
    # ─────────────────────────────────────────────────────────────────────

    async def get_status(self) -> dict:
        account = await self.broker.get_account()
        return {
            "mode":        self.mode,
            "equity":      account.equity,
            "daily_pnl":   self._daily_pnl,
            "drawdown":    self.risk.drawdown_pct,
            "positions":   len(self._positions),
            "open_pos":    self._positions,
            "total_return": (account.equity - self._start_equity) / self._start_equity * 100,
        }
