"""
[Paky] TradingIA — Fully Automated Engine v2
Integra:
  - SignalBus: comunica con la GUI in tempo reale
  - TrendChangeDetector: monitora tutti gli strumenti ogni 15 minuti
  - Comandi manuali dalla GUI (open/close trade)
  - AutoConfig AI pipeline (ogni ora per strumento)

Flusso per ciclo:
  1. Fetch candle 4H e 1H per tutti gli strumenti
  2. TrendChangeDetector → emette TrendAlertEvent se confidence > 60
  3. Applica strategia corretta (trend_4h / range_1h)
  4. Risk Manager valuta il segnale
  5. Esegue ordine sul broker
  6. Controlla SL/TP delle posizioni aperte
  7. Aggiorna GUI via SignalBus
  8. Controlla comandi manuali dalla GUI
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone, time as dtime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from brokers.paper_broker import PaperBroker
from core.signal_bus import (
    get_bus,
    ScanResultEvent, TradeOpenedEvent, TradeClosedEvent,
    PositionUpdateEvent, TrendAlertEvent, EngineStatusEvent,
    OpenTradeCommand, CloseTradeCommand,
)
from indicators.trend_change import TrendChangeDetector
from notifications.notifier import notifier
from risk.risk_manager import RiskManager
from strategies.base_strategy import TradeSignal
from strategies.trend_4h import TrendStrategy4H
from strategies.range_1h import RangeStrategy1H
from utils.logger import get_logger

logger = get_logger.bind(name="engine")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAZIONE STRUMENTI
# [Chloe] Selezione finale: liquidi, spread bassi
# ─────────────────────────────────────────────────────────────────────────────

INSTRUMENTS = {
    # symbol_yf  : (display,   strategy,   asset_class,  pip_size)
    "EURUSD=X"   : ("EUR/USD", "trend_4h", "forex",      0.00001),
    "GBPUSD=X"   : ("GBP/USD", "trend_4h", "forex",      0.00001),
    "XAUUSD=X"   : ("XAU/USD", "trend_4h", "commodity",  0.01),
    "^GSPC"      : ("S&P 500", "trend_4h", "index",      0.01),
    "^GDAXI"     : ("DAX 40",  "trend_4h", "index",      0.01),
    "EURGBP=X"   : ("EUR/GBP", "range_1h", "forex",      0.00001),
    "JPY=X"      : ("USD/JPY", "range_1h", "forex",      0.001),
}

# [Chloe] Sessioni operative (UTC)
TRADING_HOURS = {
    "forex":     (dtime(7, 0),  dtime(21, 0)),
    "commodity": (dtime(8, 0),  dtime(20, 0)),
    "index":     (dtime(8, 0),  dtime(21, 30)),
}

SCAN_INTERVAL_4H    = 60 * 60 * 4   # secondi
SCAN_INTERVAL_1H    = 60 * 60
TREND_SCAN_INTERVAL = 60 * 15       # trend detector ogni 15min
POSITION_CHECK      = 30
STATUS_INTERVAL     = 30

STATE_FILE = Path.home() / ".tradingia_engine_state.json"


# ─────────────────────────────────────────────────────────────────────────────
class TradingEngine:
    """Motore di trading completamente automatico con integrazione GUI."""

    def __init__(
        self,
        capital: float = 1000.0,
        mode: str = "paper",
        broker=None,
    ):
        self.capital      = capital
        self.mode         = mode
        self.broker       = broker or PaperBroker(initial_capital=capital, commission_pct=0.0001)
        self.risk         = RiskManager()
        self.trend_strat  = TrendStrategy4H()
        self.range_strat  = RangeStrategy1H()
        self.trend_det    = TrendChangeDetector()
        self.bus          = get_bus()

        self._positions: Dict[str, dict] = {}
        self._running       = False
        self._last_scan: Dict[str, datetime]        = {}
        self._last_trend_scan: Dict[str, datetime]  = {}
        self._daily_pnl     = 0.0
        self._start_equity  = capital
        self._candle_cache: Dict[str, pd.DataFrame] = {}

    # ─────────────────────────────────────────────────────────────────────
    # Entry point
    # ─────────────────────────────────────────────────────────────────────

    async def run(self):
        logger.info(f"Engine avviato | modo={self.mode} | capitale=€{self.capital:,.2f}")
        await self.broker.connect()
        self.bus.emit_started()
        self.bus.emit_log(
            f"Engine avviato — {self.mode.upper()} €{self.capital:,.2f}", "#3fb950"
        )

        await notifier.notify_alert(
            "TradingIA Avviato",
            f"Modo: {self.mode.upper()} | Capitale: €{self.capital:,.2f}\n"
            f"Strumenti: {len(INSTRUMENTS)} | Trend Detector: ON"
        )

        self._running = True
        self._load_state()

        await asyncio.gather(
            self._scan_loop(),
            self._trend_detect_loop(),
            self._position_monitor_loop(),
            self._gui_command_loop(),
            self._status_loop(),
        )

    async def stop(self):
        self._running = False
        self._save_state()
        self.bus.emit_stopped()
        self.bus.emit_log("Engine fermato.", "#e3b341")
        logger.info("Engine fermato.")

    # ─────────────────────────────────────────────────────────────────────
    # Loop: scansione segnali
    # ─────────────────────────────────────────────────────────────────────

    async def _scan_loop(self):
        while self._running:
            now = datetime.now(timezone.utc)

            for symbol, (display, strategy, asset_class, pip) in INSTRUMENTS.items():
                try:
                    if not self._in_session(now, asset_class):
                        continue
                    if now.weekday() == 4 and now.hour >= 20:
                        continue
                    if now.weekday() == 6:
                        continue

                    interval = SCAN_INTERVAL_4H if strategy == "trend_4h" else SCAN_INTERVAL_1H
                    last = self._last_scan.get(symbol)
                    if last and (now - last).total_seconds() < interval:
                        continue

                    self._last_scan[symbol] = now
                    tf = "4h" if strategy == "trend_4h" else "1h"
                    df = await self._fetch_candles(symbol, tf)
                    if df is None or len(df) < 40:
                        continue

                    self._candle_cache[symbol] = df
                    price = float(df["close"].iloc[-1])
                    self.broker.set_price(symbol, price)

                    # Genera segnale
                    sig = (
                        self.trend_strat.compute(df, symbol)
                        if strategy == "trend_4h"
                        else self.range_strat.compute(df, symbol)
                    )

                    # Emetti al bus (mostra nella GUI anche "none")
                    self.bus.emit_scan_result(ScanResultEvent(
                        symbol=symbol, display=display,
                        direction=sig.direction, confidence=sig.confidence,
                        strategy=sig.strategy, reason=sig.reason,
                    ))
                    self.bus.emit_log(
                        f"{display}: {sig.direction.upper()} conf={sig.confidence:.2f} — {sig.reason}",
                        "#3fb950" if sig.direction == "buy" else
                        "#f85149" if sig.direction == "sell" else "#8b949e"
                    )

                    if sig.direction == "none" or symbol in self._positions:
                        continue

                    # Risk check
                    account = await self.broker.get_account()
                    self.risk.update_portfolio(account.equity, self._positions, self._daily_pnl)
                    trade_sig = TradeSignal(
                        symbol=symbol, direction=sig.direction,
                        confidence=sig.confidence,
                        stop_loss=sig.stop_loss, take_profit=sig.take_profit,
                        strategy=sig.strategy,
                    )
                    assessment = self.risk.evaluate(trade_sig, price)

                    if not assessment.approved:
                        self.bus.emit_log(f"{display}: rifiutato — {assessment.reason}", "#e3b341")
                        continue

                    await self._execute_trade(symbol, display, sig, assessment, price, pip)

                except Exception as e:
                    logger.error(f"Errore scan {symbol}: {e}")
                    self.bus.emit_log(f"Errore scan {display}: {e}", "#f85149")

            await asyncio.sleep(60)

    # ─────────────────────────────────────────────────────────────────────
    # Loop: trend change detection (ogni 15 min, tutti gli strumenti)
    # ─────────────────────────────────────────────────────────────────────

    async def _trend_detect_loop(self):
        while self._running:
            now = datetime.now(timezone.utc)

            for symbol, (display, strategy, asset_class, _pip) in INSTRUMENTS.items():
                try:
                    last = self._last_trend_scan.get(symbol)
                    if last and (now - last).total_seconds() < TREND_SCAN_INTERVAL:
                        continue

                    self._last_trend_scan[symbol] = now

                    # Usa cache se disponibile, altrimenti fetch
                    df = self._candle_cache.get(symbol)
                    if df is None:
                        tf = "4h" if strategy == "trend_4h" else "1h"
                        df = await self._fetch_candles(symbol, tf)
                    if df is None or len(df) < 40:
                        continue

                    tf = "4h" if strategy == "trend_4h" else "1h"
                    alert = self.trend_det.analyze(df, symbol, tf)

                    if alert is None:
                        continue

                    # Emetti solo se confidence significativa
                    if alert.confidence < 30:
                        continue

                    self.bus.emit_trend_alert(TrendAlertEvent(
                        symbol=symbol,
                        display=display,
                        alert_type=alert.alert_type,
                        confidence=alert.confidence,
                        signals=alert.active_signals,
                        description=alert.description,
                        timeframe=tf,
                    ))

                    level = "FORTE" if alert.is_strong() else "DEBOLE"
                    color = "#3fb950" if "bull" in alert.alert_type else "#f85149"
                    self.bus.emit_log(
                        f"TREND ALERT {level} | {display} | {alert.alert_type} | "
                        f"conf={alert.confidence:.0f}% | segnali: {', '.join(alert.active_signals[:2])}",
                        color,
                    )

                    # Notifica Telegram solo per alert forti
                    if alert.is_strong():
                        await notifier.notify_alert(
                            f"Trend Change Alert: {display}",
                            alert.description
                        )

                except Exception as e:
                    logger.error(f"Errore trend detect {symbol}: {e}")

            await asyncio.sleep(60)

    # ─────────────────────────────────────────────────────────────────────
    # Loop: monitor posizioni ogni 30s
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

                    # Aggiorna P&L live nella GUI
                    entry = pos["entry"]
                    qty   = pos["quantity"]
                    if pos["direction"] == "buy":
                        pnl     = (price - entry) * qty
                        pnl_pct = (price - entry) / entry * 100
                    else:
                        pnl     = (entry - price) * qty
                        pnl_pct = (entry - price) / entry * 100

                    self.bus.emit_position_update(PositionUpdateEvent(
                        symbol=symbol, display=pos["display"],
                        direction=pos["direction"], quantity=qty,
                        entry_price=entry, current_price=price,
                        unrealized_pnl=round(pnl, 2),
                        pnl_pct=round(pnl_pct, 3),
                        stop_loss=pos["sl"], take_profit=pos["tp"],
                    ))

                    # Controlla SL/TP
                    exit_reason = self.risk.check_stops(
                        symbol=symbol, direction=pos["direction"],
                        current_price=price,
                        stop_loss=pos["sl"], take_profit=pos["tp"],
                    )
                    if exit_reason:
                        await self._close_position(symbol, price, exit_reason)

                except Exception as e:
                    logger.error(f"Errore monitor {symbol}: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Loop: comandi manuali dalla GUI
    # ─────────────────────────────────────────────────────────────────────

    async def _gui_command_loop(self):
        while self._running:
            cmd = await self.bus.get_command_nowait()
            if cmd is None:
                await asyncio.sleep(0.5)
                continue

            try:
                if isinstance(cmd, OpenTradeCommand):
                    await self._handle_manual_open(cmd)
                elif isinstance(cmd, CloseTradeCommand):
                    df = await self._fetch_candles(cmd.symbol, "5m", bars=3)
                    price = float(df["close"].iloc[-1]) if df is not None else 0
                    if price > 0:
                        await self._close_position(cmd.symbol, price, "manual")
            except Exception as e:
                logger.error(f"Errore comando GUI: {e}")
                self.bus.emit_log(f"Errore comando manuale: {e}", "#f85149")

    async def _handle_manual_open(self, cmd: OpenTradeCommand):
        info = INSTRUMENTS.get(cmd.symbol)
        if info is None:
            self.bus.emit_log(f"Strumento sconosciuto: {cmd.symbol}", "#f85149")
            return

        display, strategy, asset_class, pip = info

        if cmd.symbol in self._positions:
            self.bus.emit_log(f"{display}: posizione già aperta", "#e3b341")
            return

        df = await self._fetch_candles(cmd.symbol, "1h", bars=60)
        if df is None:
            self.bus.emit_log(f"{display}: no dati per prezzo", "#f85149")
            return

        price = float(df["close"].iloc[-1])
        self.broker.set_price(cmd.symbol, price)

        # SL/TP automatici se non specificati
        sl = cmd.stop_loss
        tp = cmd.take_profit
        if sl == 0 or tp == 0:
            from strategies.trend_4h import TrendStrategy4H as _T
            atr_val = _T._atr(
                df["high"].values, df["low"].values, df["close"].values, 14
            )[-1]
            if cmd.direction == "buy":
                sl = sl or round(price - 2.0 * atr_val, 5)
                tp = tp or round(price + 3.0 * atr_val, 5)
            else:
                sl = sl or round(price + 2.0 * atr_val, 5)
                tp = tp or round(price - 3.0 * atr_val, 5)

        result = await self.broker.place_order(
            symbol=cmd.symbol, direction=cmd.direction,
            quantity=cmd.quantity, order_type="market",
        )
        if not result.success:
            self.bus.emit_log(f"{display}: ordine manuale fallito", "#f85149")
            return

        self._positions[cmd.symbol] = {
            "direction": cmd.direction, "quantity": cmd.quantity,
            "entry": price, "sl": sl, "tp": tp,
            "strategy": "manual", "opened_at": datetime.utcnow().isoformat(),
            "display": display, "pip": pip,
        }
        self._save_state()

        self.bus.emit_trade_opened(TradeOpenedEvent(
            symbol=cmd.symbol, display=display,
            direction=cmd.direction, quantity=cmd.quantity,
            entry_price=price, stop_loss=sl, take_profit=tp,
            strategy="manual", risk_eur=0.0,
        ))
        self.bus.emit_log(
            f"MANUALE: {cmd.direction.upper()} {display} @ {price:.5f} | SL={sl:.5f} TP={tp:.5f}",
            "#3fb950" if cmd.direction == "buy" else "#f85149",
        )

    # ─────────────────────────────────────────────────────────────────────
    # Loop: status heartbeat alla GUI
    # ─────────────────────────────────────────────────────────────────────

    async def _status_loop(self):
        while self._running:
            await asyncio.sleep(STATUS_INTERVAL)
            try:
                account = await self.broker.get_account()
                self.bus.emit_engine_status(EngineStatusEvent(
                    running=True,
                    mode=self.mode,
                    equity=account.equity,
                    daily_pnl=self._daily_pnl,
                    drawdown_pct=self.risk.drawdown_pct,
                    open_positions=len(self._positions),
                    total_return_pct=(account.equity - self._start_equity) / self._start_equity * 100,
                    last_scan=datetime.utcnow().strftime("%H:%M:%S"),
                ))
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────
    # Esecuzione trade
    # ─────────────────────────────────────────────────────────────────────

    async def _execute_trade(self, symbol, display, sig, assessment, price, pip):
        result = await self.broker.place_order(
            symbol=symbol, direction=sig.direction,
            quantity=assessment.quantity, order_type="market",
        )
        if not result.success:
            return

        self._positions[symbol] = {
            "direction": sig.direction, "quantity": assessment.quantity,
            "entry": price, "sl": assessment.stop_loss, "tp": assessment.take_profit,
            "strategy": sig.strategy, "opened_at": datetime.utcnow().isoformat(),
            "display": display, "pip": pip,
        }
        self._save_state()

        rr = (abs(sig.take_profit - price) / abs(price - assessment.stop_loss)
              if abs(price - assessment.stop_loss) > 1e-8 else 0)

        self.bus.emit_trade_opened(TradeOpenedEvent(
            symbol=symbol, display=display,
            direction=sig.direction, quantity=assessment.quantity,
            entry_price=price,
            stop_loss=assessment.stop_loss, take_profit=assessment.take_profit,
            strategy=sig.strategy,
            risk_eur=round(assessment.max_loss_usd, 2),
        ))
        self.bus.emit_log(
            f"TRADE APERTO: {sig.direction.upper()} {display} @ {price:.5f} "
            f"| R/R 1:{rr:.1f} | rischio €{assessment.max_loss_usd:.2f}",
            "#3fb950" if sig.direction == "buy" else "#f85149",
        )

        await notifier.notify_trade(display, sig.direction, assessment.quantity, price)
        await notifier.notify_alert(
            f"Trade: {display}",
            f"{sig.direction.upper()} @ {price:.5f}\n"
            f"SL: {assessment.stop_loss:.5f} | TP: {assessment.take_profit:.5f}\n"
            f"R/R: 1:{rr:.1f} | Rischio: €{assessment.max_loss_usd:.2f}\n"
            f"Motivo: {sig.reason}"
        )

    async def _close_position(self, symbol: str, price: float, reason: str):
        pos = self._positions.pop(symbol, None)
        if not pos:
            return

        close_dir = "sell" if pos["direction"] == "buy" else "buy"
        result = await self.broker.place_order(
            symbol=symbol, direction=close_dir,
            quantity=pos["quantity"], order_type="market",
        )
        if not result.success:
            self._positions[symbol] = pos
            return

        pnl = ((price - pos["entry"]) * pos["quantity"]
               if pos["direction"] == "buy"
               else (pos["entry"] - price) * pos["quantity"])

        self._daily_pnl += pnl
        self._save_state()

        self.bus.emit_trade_closed(TradeClosedEvent(
            symbol=symbol, display=pos["display"],
            direction=pos["direction"], quantity=pos["quantity"],
            entry_price=pos["entry"], exit_price=price,
            pnl=round(pnl, 2), reason=reason,
        ))
        emoji = "✅" if pnl > 0 else "❌"
        self.bus.emit_log(
            f"{emoji} CHIUSO: {pos['display']} | {reason} | P&L €{pnl:+.2f}",
            "#3fb950" if pnl > 0 else "#f85149",
        )

        await notifier.notify_trade(pos["display"], close_dir, pos["quantity"], price, pnl)

    # ─────────────────────────────────────────────────────────────────────
    # Data feed
    # ─────────────────────────────────────────────────────────────────────

    async def _fetch_candles(
        self, symbol: str, timeframe: str, bars: int = 120
    ) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            interval_map  = {"5m": "5m", "1h": "1h", "4h": "1h"}
            period_map     = {"5m": "5d", "1h": "60d", "4h": "60d"}
            interval = interval_map.get(timeframe, "1h")
            period   = period_map.get(timeframe, "60d")

            df = await asyncio.to_thread(
                lambda: yf.download(symbol, period=period, interval=interval,
                                    auto_adjust=True, progress=False)
            )
            if df is None or len(df) == 0:
                return None

            df.columns = [
                (c.lower() if isinstance(c, str) else c[0].lower())
                for c in df.columns
            ]

            if timeframe == "4h":
                df = df.resample("4h").agg({
                    "open": "first", "high": "max",
                    "low": "min", "close": "last", "volume": "sum",
                }).dropna()

            return df.tail(bars)
        except Exception as e:
            logger.warning(f"Feed {symbol}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _in_session(now_utc: datetime, asset_class: str) -> bool:
        hours = TRADING_HOURS.get(asset_class, (dtime(0, 0), dtime(23, 59)))
        t = now_utc.time().replace(tzinfo=None)
        return hours[0] <= t <= hours[1]

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
                    logger.info(f"Stato ripristinato: {len(self._positions)} posizioni")
                    self.bus.emit_log(
                        f"Stato ripristinato: {len(self._positions)} posizioni aperte", "#e3b341"
                    )
        except Exception:
            pass

    async def get_status(self) -> dict:
        account = await self.broker.get_account()
        return {
            "mode":         self.mode,
            "equity":       account.equity,
            "daily_pnl":    self._daily_pnl,
            "drawdown":     self.risk.drawdown_pct,
            "positions":    len(self._positions),
            "open_pos":     self._positions,
            "total_return": (account.equity - self._start_equity) / self._start_equity * 100,
        }
