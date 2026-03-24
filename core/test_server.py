"""
TestServer — TCP server embedded nell'app per testing autonomo.

Ascolta su 127.0.0.1:7779.
Ogni client connesso riceve:
  - gli ultimi 100 log entries al momento della connessione
  - tutti i nuovi log in tempo reale (streaming)
  - le risposte ai comandi JSON inviati

Protocollo: newline-delimited JSON su TCP.

  Client → Server:  {"cmd": "...", ...}\\n
  Server → Client:  {"status": "ok", "result": {...}}\\n
                    {"status": "error", "message": "..."}\\n
                    {"type": "log", "level": "...", "name": "...", "msg": "...", "time": "..."}\\n

Comandi supportati:
  ping                                     — health check
  get_logs          {n}                    — ultimi N log dal buffer
  get_ohlcv         {symbol, timeframe, limit}
  run_indicators    {symbol, timeframe}    — RSI, MACD, CCI, ATR, BB, VWAP
  run_backtest      {symbol, strategy, timeframe, capital, days}
  run_signal        {symbol, strategy, timeframe}
  get_status                               — PID, memoria, CPU
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Set

from utils.logger import get_logger

logger = get_logger.bind(name="core.test_server")

HOST = "127.0.0.1"
PORT = 7779


# ── Strategy builder (condiviso con backtest_panel) ───────────────────────────

def _build_strategy(name: str, timeframe: str):
    try:
        from strategies.technical_strategy import (
            TrendFollowingStrategy, MeanReversionStrategy,
            BreakoutStrategy, ScalpingStrategy,
        )
        from strategies.ai_strategy import AIStrategy
        mapping = {
            "trend_following": TrendFollowingStrategy,
            "mean_reversion":  MeanReversionStrategy,
            "breakout":        BreakoutStrategy,
            "scalping":        ScalpingStrategy,
            "ai_ensemble":     AIStrategy,
        }
        cls = mapping.get(name)
        return cls(timeframe=timeframe) if cls else None
    except Exception as e:
        logger.debug(f"_build_strategy error: {e}")
        return None


# ── Server principale ─────────────────────────────────────────────────────────

class TestServer:
    """Server TCP per testing autonomo dell'app."""

    def __init__(self):
        self._clients: Set[asyncio.StreamWriter] = set()
        self._log_buffer: list = []          # ultimi 200 log
        self._server: asyncio.AbstractServer | None = None

    # ── Avvio ──────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, HOST, PORT
        )
        logger.info(f"TestServer in ascolto su {HOST}:{PORT}")

    def stop(self) -> None:
        if self._server:
            self._server.close()

    # ── Sink loguru ────────────────────────────────────────────────────────

    def loguru_sink(self, message) -> None:
        """
        Sink loguru: chiamato per ogni log entry.
        Aggiunge al buffer circolare e fa broadcast a tutti i client.
        writer.write() è thread-safe con asyncio (aggiunge solo al buffer interno).
        """
        record = message.record
        entry = {
            "type": "log",
            "time": record["time"].strftime("%H:%M:%S"),
            "level": record["level"].name,
            "name":  record["name"],
            "line":  record["line"],
            "msg":   record["message"],
        }
        self._log_buffer.append(entry)
        if len(self._log_buffer) > 200:
            self._log_buffer.pop(0)

        line = (json.dumps(entry) + "\n").encode()
        for writer in list(self._clients):
            try:
                if not writer.is_closing():
                    writer.write(line)
            except Exception:
                self._clients.discard(writer)

    # ── Gestione client ────────────────────────────────────────────────────

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        addr = writer.get_extra_info("peername")
        self._clients.add(writer)
        logger.debug(f"TestServer: client connesso da {addr}")

        # Invia gli ultimi 100 log al nuovo client
        try:
            for entry in self._log_buffer[-100:]:
                writer.write((json.dumps(entry) + "\n").encode())
            await writer.drain()
        except Exception:
            pass

        # Loop comandi
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                await self._dispatch(line, writer)
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug(f"TestServer client error: {e}")
        finally:
            self._clients.discard(writer)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"TestServer: client {addr} disconnesso")

    async def _dispatch(
        self,
        data: bytes,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            cmd = json.loads(data)
            result = await self._execute(cmd)
            resp = json.dumps({"status": "ok", "result": result}) + "\n"
        except json.JSONDecodeError as e:
            resp = json.dumps({"status": "error", "message": f"JSON invalido: {e}"}) + "\n"
        except Exception as e:
            resp = json.dumps({"status": "error", "message": str(e)}) + "\n"

        try:
            writer.write(resp.encode())
            await writer.drain()
        except Exception:
            pass

    # ── Esecuzione comandi ─────────────────────────────────────────────────

    async def _execute(self, cmd: dict) -> dict:
        name = cmd.get("cmd", "")

        # ── ping ──────────────────────────────────────────────────────────
        if name == "ping":
            return {"pong": True, "timestamp": datetime.utcnow().isoformat()}

        # ── get_logs ──────────────────────────────────────────────────────
        elif name == "get_logs":
            n = int(cmd.get("n", 50))
            return {"logs": self._log_buffer[-n:], "total_buffered": len(self._log_buffer)}

        # ── get_ohlcv ─────────────────────────────────────────────────────
        elif name == "get_ohlcv":
            symbol   = cmd["symbol"]
            tf       = cmd.get("timeframe", "1h")
            limit    = int(cmd.get("limit", 100))
            from data.feed import data_feed
            df = await data_feed.get_ohlcv(symbol, tf, limit=limit)
            if df is None or df.empty:
                return {"bars": 0, "symbol": symbol, "timeframe": tf}
            return {
                "symbol":     symbol,
                "timeframe":  tf,
                "bars":       len(df),
                "from":       str(df.index[0]),
                "to":         str(df.index[-1]),
                "last_close": round(float(df["close"].iloc[-1]), 4),
                "last_volume":round(float(df["volume"].iloc[-1]), 0),
                "has_nan":    int(df[["open","high","low","close"]].isna().sum().sum()),
            }

        # ── run_indicators ────────────────────────────────────────────────
        elif name == "run_indicators":
            symbol = cmd["symbol"]
            tf     = cmd.get("timeframe", "1h")
            from data.feed import data_feed
            from indicators.technical import TechnicalIndicators
            import numpy as np

            df = await data_feed.get_ohlcv(symbol, tf, limit=200)
            if df is None or df.empty:
                return {"error": f"nessun dato per {symbol}"}

            result_df = TechnicalIndicators.compute_all(df)
            last      = result_df.iloc[-1]

            def _v(col):
                v = last.get(col, float("nan"))
                return None if (v is None or (isinstance(v, float) and np.isnan(v))) else round(float(v), 4)

            nan_total  = int(result_df.tail(20).isna().sum().sum())
            nan_cols   = [c for c in result_df.columns if result_df[c].isna().any()]

            return {
                "symbol":    symbol,
                "timeframe": tf,
                "rsi_14":    _v("rsi_14"),
                "rsi_7":     _v("rsi_7"),
                "macd":      _v("macd"),
                "macd_hist": _v("macd_hist"),
                "cci_20":    _v("cci_20"),
                "atr_14":    _v("atr_14"),
                "bb_pct":    _v("bb_pct"),
                "vwap":      _v("vwap"),
                "stoch_k":   _v("stoch_k"),
                "nan_in_last_20_bars": nan_total,
                "cols_with_nan":       nan_cols[:10],
            }

        # ── run_backtest ──────────────────────────────────────────────────
        elif name == "run_backtest":
            symbol        = cmd.get("symbol", "AAPL")
            strategy_name = cmd.get("strategy", "trend_following")
            tf            = cmd.get("timeframe", "1h")
            capital       = float(cmd.get("capital", 10_000.0))
            days          = int(cmd.get("days", 60))

            from data.feed import data_feed
            from backtesting.backtester import Backtester

            hours_per_bar = {"1m": 1/60, "5m": 1/12, "15m": 1/4,
                             "30m": 1/2, "1h": 1, "4h": 4, "1d": 24}
            h     = hours_per_bar.get(tf, 1)
            limit = max(300, int(days * 24 / h))

            df = await data_feed.get_ohlcv(symbol, tf, limit=limit)
            if df is None or df.empty:
                return {"error": f"nessun dato per {symbol}"}

            strategy = _build_strategy(strategy_name, tf)
            if strategy is None:
                return {"error": f"strategia sconosciuta: {strategy_name}"}

            bt     = Backtester(initial_capital=capital)
            result = bt.run(df, strategy, symbol, progress_callback=lambda _: None)

            return {
                "symbol":           symbol,
                "strategy":         strategy_name,
                "timeframe":        tf,
                "bars":             len(df),
                "trades":           result.total_trades,
                "winning_trades":   result.winning_trades,
                "losing_trades":    result.losing_trades,
                "win_rate":         round(result.win_rate, 1),
                "total_return_pct": round(result.total_return_pct, 2),
                "annual_return_pct":round(result.annualized_return_pct, 2),
                "sharpe":           round(result.sharpe_ratio, 3),
                "sortino":          round(result.sortino_ratio, 3),
                "max_drawdown_pct": round(result.max_drawdown_pct, 2),
                "profit_factor":    round(result.profit_factor, 3),
                "avg_win_pct":      round(result.avg_win_pct, 2),
                "avg_loss_pct":     round(result.avg_loss_pct, 2),
                "final_capital":    round(result.final_capital, 2),
            }

        # ── run_signal ────────────────────────────────────────────────────
        elif name == "run_signal":
            symbol        = cmd["symbol"]
            strategy_name = cmd.get("strategy", "trend_following")
            tf            = cmd.get("timeframe", "1h")

            from data.feed import data_feed
            from indicators.technical import TechnicalIndicators

            df = await data_feed.get_ohlcv(symbol, tf, limit=200)
            if df is None or df.empty:
                return {"error": f"nessun dato per {symbol}"}

            strategy = _build_strategy(strategy_name, tf)
            if strategy is None:
                return {"error": f"strategia sconosciuta: {strategy_name}"}

            df_ind = TechnicalIndicators.compute_all(df)
            df_ind = df_ind.dropna(subset=["rsi_14", "macd"])
            if df_ind.empty:
                return {"error": "dati insufficienti dopo dropna"}

            try:
                signals = strategy.generate_signals(symbol, df_ind)
            except Exception as e:
                return {"error": f"generate_signals error: {e}"}

            return {
                "symbol":   symbol,
                "strategy": strategy_name,
                "signals":  [
                    {
                        "direction":    s.direction,
                        "confidence":   round(s.confidence, 3),
                        "is_actionable":s.is_actionable,
                        "stop_loss":    round(s.stop_loss, 4) if s.stop_loss else None,
                        "take_profit":  round(s.take_profit, 4) if s.take_profit else None,
                    }
                    for s in signals
                ],
            }

        # ── get_status ────────────────────────────────────────────────────
        elif name == "get_status":
            try:
                import psutil
                proc = psutil.Process(os.getpid())
                return {
                    "pid":        os.getpid(),
                    "memory_mb":  round(proc.memory_info().rss / 1024 / 1024, 1),
                    "cpu_pct":    round(proc.cpu_percent(interval=0.05), 1),
                    "clients":    len(self._clients),
                    "log_buffer": len(self._log_buffer),
                }
            except ImportError:
                return {
                    "pid":        os.getpid(),
                    "clients":    len(self._clients),
                    "log_buffer": len(self._log_buffer),
                    "note":       "installa psutil per info memoria/CPU",
                }

        else:
            raise ValueError(
                f"Comando sconosciuto: '{name}'. "
                f"Disponibili: ping, get_logs, get_ohlcv, run_indicators, "
                f"run_backtest, run_signal, get_status"
            )


# ── Singleton ─────────────────────────────────────────────────────────────────
test_server = TestServer()
