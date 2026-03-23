"""
TradingIA Core Orchestrator
Coordinates: data feed → indicators → AI models → strategies → risk → execution
"""

import asyncio
import json
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import settings
from data.feed import UniversalDataFeed
from strategies.strategy_manager import StrategyManager
from strategies.base_strategy import TradeSignal
from risk.risk_manager import RiskManager
from portfolio.portfolio_manager import PortfolioManager
from notifications.notifier import notifier
from database.db import init_db
from utils.logger import get_logger

_RETRAIN_STAMP_FILE = Path(settings.ml.models_dir) / ".last_retrain.json"

logger = get_logger.bind(name="orchestrator")


class TradingOrchestrator:
    """
    Main trading loop orchestrator.
    Runs continuously, processes all instruments, executes signals.
    """

    def __init__(self, broker=None, paper_mode: bool = True):
        self.paper_mode = paper_mode
        self.data_feed = UniversalDataFeed()
        self.strategy_manager = StrategyManager()
        self.risk_manager = RiskManager()
        self.portfolio = PortfolioManager(initial_capital=100_000.0)
        self.broker = broker
        self._last_signals: List[TradeSignal] = []
        self._running = False
        self._scan_interval = 60   # seconds between full scans
        self._ws_broadcast = None  # injected by dashboard

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def start(self):
        await init_db()
        logger.info(f"TradingIA starting | paper_mode={self.paper_mode}")
        logger.info(f"Instruments: {len(settings.all_symbols)} symbols across {len(settings.timeframes)} timeframes")

        if self.broker:
            connected = await self.broker.connect()
            if not connected:
                logger.error("Broker connection failed")
                return

        self._running = True

        # Retrain se il sistema non era attivo durante la finestra notturna
        if settings.ml.nightly_retrain_enabled:
            await self._retrain_if_missed()

        loops = [
            self._main_loop(),
            self._position_monitor_loop(),
            self._daily_reset_loop(),
        ]
        if settings.ml.nightly_retrain_enabled:
            loops.append(self._nightly_retrain_loop())
        await asyncio.gather(*loops)

    async def stop(self):
        self._running = False
        await self.data_feed.close()
        logger.info("TradingIA stopped")

    # ── Main scan loop ─────────────────────────────────────────────────────

    async def _main_loop(self):
        while self._running:
            start = asyncio.get_event_loop().time()
            try:
                await self._scan_cycle()
            except Exception as e:
                logger.error(f"Main loop error: {e}", exc_info=True)
            elapsed = asyncio.get_event_loop().time() - start
            sleep_time = max(0, self._scan_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _scan_cycle(self):
        """Fetch data → evaluate strategies → execute signals."""
        logger.debug("Starting scan cycle...")

        # 1. Fetch OHLCV for all symbols and primary timeframes
        symbols = settings.all_symbols
        data: Dict[str, Dict] = {}

        fetch_tasks = {
            symbol: self.data_feed.get_ohlcv(symbol, settings.primary_timeframe, limit=500)
            for symbol in symbols
        }
        results = await asyncio.gather(*fetch_tasks.values(), return_exceptions=True)

        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception) or result is None:
                continue
            data[symbol] = {settings.primary_timeframe: result}

        # 2. Fetch additional timeframes for multi-TF strategies
        for symbol in list(data.keys())[:20]:   # limit concurrent fetches
            for tf in ["1d", "4h"]:
                if tf != settings.primary_timeframe:
                    df = await self.data_feed.get_ohlcv(symbol, tf, limit=200)
                    if df is not None:
                        data[symbol][tf] = df

        # 3. Evaluate all strategies
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"Trading paused: {reason}")
            return

        all_signals = await self.strategy_manager.evaluate_all(data)

        # 4. Process signals
        new_signals = []
        for symbol, signals in all_signals.items():
            for signal in signals:
                df = data[symbol].get(settings.primary_timeframe)
                if df is None:
                    continue

                from indicators.technical import TechnicalIndicators
                import pandas as pd
                atr_series = TechnicalIndicators.atr(df["high"], df["low"], df["close"], 14)
                atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else None
                current_price = float(df["close"].iloc[-1])

                # Risk assessment
                assessment = self.risk_manager.evaluate(signal, current_price, atr)
                if not assessment.approved:
                    continue

                # Execute
                await self._execute_signal(signal, assessment, current_price)
                new_signals.append(signal)

        if new_signals:
            self._last_signals = (new_signals + self._last_signals)[:50]
            await self._broadcast({"type": "signal", "count": len(new_signals)})

        logger.info(f"Scan complete. Symbols: {len(data)}, Signals: {sum(len(v) for v in all_signals.values())}, Executed: {len(new_signals)}")

    # ── Execution ──────────────────────────────────────────────────────────

    async def _execute_signal(self, signal: TradeSignal, assessment, price: float):
        """Place order with broker and update portfolio."""
        asset_type = settings.asset_type_map.get(signal.symbol, "stock")

        if self.broker:
            result = await self.broker.place_order(
                signal.symbol,
                signal.direction,
                assessment.quantity,
            )
            if not result.success:
                logger.error(f"Order failed: {signal.symbol} - {result.message}")
                return
            fill_price = result.price or price
        else:
            fill_price = price

        # Update internal portfolio
        self.portfolio.open_position(
            symbol=signal.symbol,
            asset_type=asset_type,
            direction=signal.direction,
            quantity=assessment.quantity,
            price=fill_price,
            stop_loss=assessment.stop_loss,
            take_profit=assessment.take_profit,
            trailing_stop=assessment.trailing_stop,
            strategy=signal.strategy_name,
            risk_usd=assessment.max_loss_usd,
        )

        # Update risk manager
        self.risk_manager.update_portfolio(
            equity=self.portfolio.total_equity,
            positions={s: {"risk_usd": p.risk_usd} for s, p in self.portfolio.positions.items()},
        )

        await notifier.notify_trade(signal.symbol, signal.direction, assessment.quantity, fill_price)
        logger.info(
            f"TRADE EXECUTED | {signal.direction.upper()} {assessment.quantity:.4f} "
            f"{signal.symbol} @ {fill_price:.5f} | "
            f"SL={assessment.stop_loss:.5f} TP={assessment.take_profit:.5f} | "
            f"risk={assessment.risk_pct:.2f}%"
        )

    # ── Position monitor ───────────────────────────────────────────────────

    async def _position_monitor_loop(self):
        """Check stops and trailing stops every 10 seconds."""
        while self._running:
            await asyncio.sleep(10)
            if not self.portfolio.positions:
                continue
            try:
                await self._check_positions()
            except Exception as e:
                logger.error(f"Position monitor error: {e}")

    async def _check_positions(self):
        symbols = list(self.portfolio.positions.keys())
        quotes = await self.data_feed.get_multiple_quotes(symbols)

        to_close = []
        for symbol, pos in self.portfolio.positions.items():
            if symbol not in quotes:
                continue
            price = quotes[symbol].get("price")
            if price is None:
                continue

            pos.current_price = float(price)

            # Trailing stop update
            if pos.trailing_stop is not None:
                new_trail = self.risk_manager.update_trailing_stop(
                    symbol, pos.direction, float(price), pos.trailing_stop
                )
                if new_trail is not None:
                    pos.trailing_stop = new_trail

            # Check stop/TP
            sl = pos.trailing_stop or pos.stop_loss
            tp = pos.take_profit
            if sl and tp:
                reason = self.risk_manager.check_stops(symbol, pos.direction, float(price), sl, tp)
                if reason:
                    to_close.append((symbol, float(price), reason))

        # Close triggered positions
        for symbol, price, reason in to_close:
            trade = self.portfolio.close_position(symbol, price, reason)
            if trade:
                await notifier.notify_trade(
                    symbol, "close", trade["quantity"], price, trade["pnl"]
                )
                self.risk_manager.update_portfolio(
                    equity=self.portfolio.total_equity,
                    positions={s: {"risk_usd": p.risk_usd} for s, p in self.portfolio.positions.items()},
                )
                await self._broadcast({"type": "trade", "symbol": symbol})

        # Update live prices for all open positions
        price_map = {s: float(q["price"]) for s, q in quotes.items() if q.get("price")}
        self.portfolio.update_prices(price_map)

    # ── Daily reset ────────────────────────────────────────────────────────

    async def _daily_reset_loop(self):
        while self._running:
            now = datetime.utcnow()
            next_reset = datetime(now.year, now.month, now.day, 0, 1, 0)
            if next_reset <= now:
                next_reset = next_reset.replace(day=now.day + 1)
            wait_secs = (next_reset - now).total_seconds()
            await asyncio.sleep(wait_secs)
            self.portfolio.reset_daily()
            logger.info("Daily portfolio stats reset")

    # ── Broadcast ──────────────────────────────────────────────────────────

    async def _broadcast(self, data: dict):
        if self._ws_broadcast:
            await self._ws_broadcast(data)

    # ── Model training ─────────────────────────────────────────────────────

    async def retrain_all_models(
        self,
        symbols: List[str] = None,
        timeframe: str = "1h",
        incremental: bool = True,
    ):
        """
        Addestra / aggiorna i modelli AI per tutti i simboli dati.

        incremental=False (--full):
            Scarica il massimo disponibile (limit=0) e riaddestra da zero.
        incremental=True (default / nightly):
            Scarica gli ultimi N giorni e aggiorna i pesi esistenti.
        """
        from models.ensemble_model import EnsembleModel
        from models.indicator_selector import IndicatorSelector

        targets = symbols or settings.stock_symbols[:5] + settings.crypto_symbols[:3]
        mode_label = "INCREMENTALE" if incremental else "COMPLETO"
        logger.info(
            f"[Training {mode_label}] {len(targets)} simboli | timeframe={timeframe}"
        )

        if incremental:
            # Ore → barre: 90 giorni × 24h per "1h", 90 giorni per "1d", ecc.
            hours_per_bar = {"1m": 1/60, "5m": 1/12, "15m": 1/4, "30m": 1/2,
                             "1h": 1, "4h": 4, "1d": 24, "1w": 168}
            h = hours_per_bar.get(timeframe, 1)
            limit = int(settings.ml.incremental_train_days * 24 / h)
        else:
            limit = 0   # full download

        selector = IndicatorSelector()

        for symbol in targets:
            safe_name = symbol.replace("/", "_").replace("=", "_").replace("^", "")
            try:
                df = await self.data_feed.get_ohlcv(symbol, timeframe, limit=limit)
                if df is None or len(df) < 200:
                    logger.warning(f"[Training] Salto {symbol}: dati insufficienti ({len(df) if df is not None else 0} barre)")
                    continue

                model = EnsembleModel(name=f"ensemble_{safe_name}")

                if incremental:
                    # Carica pesi esistenti prima di aggiornare
                    model.load()

                metrics = await asyncio.to_thread(model.train, df)
                model.save()

                # Aggiorna IndicatorSelector con le nuove importances del GBM
                if model.rf_model.model is not None:
                    asset_type = settings.asset_type_map.get(symbol, "stock")
                    selector.load_from_gbm_model(
                        model.rf_model.model,
                        asset_type=asset_type,
                    )
                    selector.save()

                logger.info(f"[Training] {symbol} OK | barre={len(df)} | {metrics}")

            except Exception as e:
                logger.error(f"[Training] Errore su {symbol}: {e}", exc_info=True)

        logger.info(f"[Training {mode_label}] Completato per {len(targets)} simboli")
        self._write_last_retrain()

    async def train_all_models(self, symbols: List[str] = None, timeframe: str = "1h"):
        """Compatibilità: delega a retrain_all_models(incremental=False)."""
        await self.retrain_all_models(symbols=symbols, timeframe=timeframe, incremental=False)

    # ── Retrain timestamp helpers ───────────────────────────────────────────

    @staticmethod
    def _read_last_retrain() -> Optional[datetime]:
        """Legge il timestamp dell'ultimo retrain da file JSON."""
        try:
            if _RETRAIN_STAMP_FILE.exists():
                data = json.loads(_RETRAIN_STAMP_FILE.read_text())
                return datetime.fromisoformat(data["ts"])
        except Exception:
            pass
        return None

    @staticmethod
    def _write_last_retrain():
        """Scrive il timestamp dell'ultimo retrain su file JSON."""
        try:
            _RETRAIN_STAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
            _RETRAIN_STAMP_FILE.write_text(
                json.dumps({"ts": datetime.utcnow().isoformat()})
            )
        except Exception as e:
            logger.warning(f"[Retrain stamp] Impossibile scrivere timestamp: {e}")

    async def _retrain_if_missed(self):
        """
        All'avvio controlla se il retraining notturno è stato saltato
        (es. app spenta di notte). Se l'ultimo retrain risale a più di
        30 ore fa, esegue subito un retraining incrementale.
        """
        last = self._read_last_retrain()
        threshold = timedelta(hours=30)   # 24h + 6h di tolleranza

        if last is None:
            logger.info("[Startup] Nessun retrain precedente trovato — skip (prima esecuzione).")
            return

        elapsed = datetime.utcnow() - last
        if elapsed > threshold:
            logger.info(
                f"[Startup] Retrain notturno saltato (ultimo: {last.strftime('%Y-%m-%d %H:%M')} UTC, "
                f"passate {elapsed.total_seconds()/3600:.1f}h). Avvio recupero..."
            )
            await self.retrain_all_models(
                timeframe=settings.primary_timeframe,
                incremental=True,
            )
        else:
            logger.info(
                f"[Startup] Retrain notturno aggiornato ({elapsed.total_seconds()/3600:.1f}h fa) — OK."
            )

    # ── Nightly retrain loop ────────────────────────────────────────────────

    async def _nightly_retrain_loop(self):
        """
        Loop in background: ogni notte alle settings.ml.nightly_retrain_hour (UTC)
        esegue un retraining incrementale di tutti i modelli.
        """
        while self._running:
            now = datetime.utcnow()
            target = now.replace(
                hour=settings.ml.nightly_retrain_hour,
                minute=5, second=0, microsecond=0,
            )
            if target <= now:
                target += timedelta(days=1)

            wait_secs = (target - now).total_seconds()
            logger.info(
                f"[Nightly retrain] Prossimo aggiornamento: {target.strftime('%Y-%m-%d %H:%M')} UTC "
                f"(tra {wait_secs/3600:.1f}h)"
            )
            await asyncio.sleep(wait_secs)

            if not self._running:
                break

            logger.info("[Nightly retrain] Avvio retraining incrementale notturno...")
            try:
                await self.retrain_all_models(
                    timeframe=settings.primary_timeframe,
                    incremental=True,
                )
            except Exception as e:
                logger.error(f"[Nightly retrain] Errore: {e}", exc_info=True)
