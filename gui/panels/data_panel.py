"""
Data Panel
Controls for downloading historical & live data, then displaying on chart.
Emits data_loaded(df, symbol, timeframe) when download completes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

_UI = Path(__file__).parent.parent / "ui" / "data_panel.ui"

TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo"]


class DataPanel(QWidget):
    """
    Data download & management panel.
    """

    # Emitted when data has been fetched and is ready to display
    data_loaded = pyqtSignal(object, str, str)   # (df, symbol, timeframe)
    # Emitted on each real-time bar update
    realtime_tick = pyqtSignal(dict, str)         # (bar_dict, symbol)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._live_task: Optional[asyncio.Task] = None
        self._live_symbol = ""

        uic.loadUi(str(_UI), self)

        # Ripristina i margini rimossi dal .ui per compatibilità PyQt6 uic
        self.headerLayout.setContentsMargins(10, 0, 10, 0)
        self.bodyLayout.setContentsMargins(12, 12, 12, 12)

        # Set default timeframe selection
        self._tf_combo.setCurrentText("1h")

        self._setup_connections()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _setup_connections(self):
        # Symbol input
        self._symbol_input.returnPressed.connect(self._on_load_clicked)

        # Quick-pick buttons
        self._btn_quick_aapl.clicked.connect(
            lambda: self._symbol_input.setText("AAPL"))
        self._btn_quick_btc.clicked.connect(
            lambda: self._symbol_input.setText("BTC-USD"))
        self._btn_quick_eurusd.clicked.connect(
            lambda: self._symbol_input.setText("EURUSD=X"))
        self._btn_quick_gspc.clicked.connect(
            lambda: self._symbol_input.setText("^GSPC"))

        # Quick timeframe buttons
        self._btn_tf_5m.clicked.connect(
            lambda: self._tf_combo.setCurrentText("5m"))
        self._btn_tf_1h.clicked.connect(
            lambda: self._tf_combo.setCurrentText("1h"))
        self._btn_tf_4h.clicked.connect(
            lambda: self._tf_combo.setCurrentText("4h"))
        self._btn_tf_1d.clicked.connect(
            lambda: self._tf_combo.setCurrentText("1d"))

        # Load / live buttons
        self._btn_load.clicked.connect(self._on_load_clicked)
        self._btn_live.clicked.connect(self._on_live_clicked)

    # ── Slots ──────────────────────────────────────────────────────────────

    def _on_load_clicked(self):
        symbol = self._symbol_input.text().strip().upper()
        if not symbol:
            self._set_status("Enter a symbol first.", error=True)
            return
        tf = self._tf_combo.currentText()
        asyncio.ensure_future(self._fetch_historical(symbol, tf))

    def _on_live_clicked(self):
        symbol = self._symbol_input.text().strip().upper()
        if not symbol:
            self._set_status("Enter a symbol first.", error=True)
            self._btn_live.setChecked(False)
            return

        if self._btn_live.isChecked():
            self._btn_live.setText("Stop Live Feed")
            self._btn_live.setStyleSheet("""
                QPushButton { background-color:#da3633; border-color:#da3633;
                              color:#ffffff; border-radius:6px; }
                QPushButton:hover { background-color:#f85149; }
            """)
            self._live_symbol = symbol
            self._live_task = asyncio.ensure_future(self._live_feed(symbol))
        else:
            self._stop_live()

    def _stop_live(self):
        if self._live_task:
            self._live_task.cancel()
            self._live_task = None
        self._btn_live.setText("Start Live Feed")
        self._btn_live.setStyleSheet("")   # reset to stylesheet
        self._btn_live.setChecked(False)
        self._set_status("Live feed stopped.")

    # ── Async workers ──────────────────────────────────────────────────────

    async def _fetch_historical(self, symbol: str, timeframe: str):
        self._btn_load.setEnabled(False)
        self._progress.setVisible(True)
        self._set_status(f"Downloading {symbol} [{timeframe}]…")

        try:
            from data.feed import data_feed
            df = await data_feed.get_ohlcv(symbol, timeframe, limit=0)
            if df is None or df.empty:
                self._set_status(f"No data found for {symbol}.", error=True)
            else:
                self._set_status(
                    f"{symbol} [{timeframe}] — {len(df)} bars "
                    f"({df.index[0] if hasattr(df.index[0], 'date') else ''} …)"
                )
                self.data_loaded.emit(df, symbol, timeframe)
                self._emit_ma_settings()
        except Exception as e:
            self._set_status(f"Error: {e}", error=True)
        finally:
            self._btn_load.setEnabled(True)
            self._progress.setVisible(False)

    async def _live_feed(self, symbol: str):
        """Poll for live quotes every 5 s and emit realtime_tick."""
        self._set_status(f"Live: {symbol} (polling every 5s)")
        try:
            from data.feed import data_feed
            while True:
                quote = await data_feed.get_quote(symbol)
                if quote:
                    self.realtime_tick.emit(quote, symbol)
                    price = quote.get("price", "--")
                    self._set_status(f"Live: {symbol}  Price: {price}")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._set_status(f"Live error: {e}", error=True)
            self._stop_live()

    # ── Helpers ────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, error: bool = False):
        color = "#f85149" if error else "#8b949e"
        self._status.setStyleSheet(f"font-size:11px; color:{color};")
        self._status.setText(msg)

    def _emit_ma_settings(self):
        """Convenience: returns current MA visibility dict."""
        return {
            "ma20":  self._chk_ma20.isChecked(),
            "ma50":  self._chk_ma50.isChecked(),
            "ma200": self._chk_ma200.isChecked(),
        }

    @property
    def ma_settings(self) -> dict:
        return self._emit_ma_settings()
