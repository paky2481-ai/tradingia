"""
Data Panel
Controls for downloading historical & live data, then displaying on chart.
Emits data_loaded(df, symbol, timeframe) when download completes.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import pandas as pd
from PyQt6.QtCore import Qt, pyqtSignal, QDateTime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QGroupBox, QCheckBox, QProgressBar, QDateTimeEdit,
    QSizePolicy,
)


TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo"]

SYMBOL_PRESETS = {
    "Stocks":  ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "SPY", "QQQ"],
    "Crypto":  ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "Forex":   ["EURUSD=X", "GBPUSD=X", "USDJPY=X"],
    "Indices": ["^GSPC", "^DJI", "^IXIC"],
}


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
        self._setup_ui()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background:#161b22; border-bottom:1px solid #30363d;")
        header.setFixedHeight(44)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        title = QLabel("Data")
        title.setObjectName("label_section")
        h_layout.addWidget(title)
        h_layout.addStretch()
        layout.addWidget(header)

        # ── Body ───────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background:#0d1117;")
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(12, 12, 12, 12)
        b_layout.setSpacing(12)

        # ── Symbol input ───────────────────────────────────────────────
        sym_group = QGroupBox("Symbol")
        sg_layout = QVBoxLayout(sym_group)
        sg_layout.setSpacing(8)

        self._symbol_input = QLineEdit()
        self._symbol_input.setPlaceholderText("AAPL, BTC-USD, EURUSD=X …")
        self._symbol_input.setFixedHeight(34)
        self._symbol_input.returnPressed.connect(self._on_load_clicked)
        sg_layout.addWidget(self._symbol_input)

        # Quick-pick buttons
        qp_layout = QHBoxLayout()
        qp_layout.setSpacing(4)
        for sym in ["AAPL", "BTC-USD", "EURUSD=X", "^GSPC"]:
            btn = QPushButton(sym)
            btn.setFixedHeight(24)
            btn.setStyleSheet("""
                QPushButton { background:#21262d; border:1px solid #30363d;
                              border-radius:4px; color:#8b949e; font-size:11px; padding:0 6px; }
                QPushButton:hover { background:#30363d; color:#e6edf3; }
            """)
            btn.clicked.connect(lambda _, s=sym: self._symbol_input.setText(s))
            qp_layout.addWidget(btn)
        sg_layout.addLayout(qp_layout)
        b_layout.addWidget(sym_group)

        # ── Timeframe ──────────────────────────────────────────────────
        tf_group = QGroupBox("Timeframe")
        tf_layout = QVBoxLayout(tf_group)

        self._tf_combo = QComboBox()
        self._tf_combo.addItems(TIMEFRAMES)
        self._tf_combo.setCurrentText("1h")
        self._tf_combo.setFixedHeight(34)
        tf_layout.addWidget(self._tf_combo)

        # Quick timeframe buttons
        qf_layout = QHBoxLayout()
        qf_layout.setSpacing(4)
        for tf in ["5m", "1h", "4h", "1d"]:
            btn = QPushButton(tf)
            btn.setFixedHeight(24)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton { background:#21262d; border:1px solid #30363d;
                              border-radius:4px; color:#8b949e; font-size:11px; padding:0 6px; }
                QPushButton:checked { background:#1f6feb22; border-color:#1f6feb; color:#58a6ff; }
                QPushButton:hover { background:#30363d; color:#e6edf3; }
            """)
            btn.clicked.connect(lambda _, t=tf: self._tf_combo.setCurrentText(t))
            qf_layout.addWidget(btn)
        tf_layout.addLayout(qf_layout)
        b_layout.addWidget(tf_group)

        # ── Options ────────────────────────────────────────────────────
        opt_group = QGroupBox("Options")
        opt_layout = QVBoxLayout(opt_group)
        opt_layout.setSpacing(6)

        self._chk_ma20  = QCheckBox("MA 20")
        self._chk_ma50  = QCheckBox("MA 50")
        self._chk_ma200 = QCheckBox("MA 200")
        self._chk_ma20.setChecked(True)
        self._chk_ma50.setChecked(True)
        self._chk_ma200.setChecked(False)

        for chk in (self._chk_ma20, self._chk_ma50, self._chk_ma200):
            opt_layout.addWidget(chk)

        b_layout.addWidget(opt_group)

        # ── Buttons ────────────────────────────────────────────────────
        self._btn_load = QPushButton("Load Historical Data")
        self._btn_load.setObjectName("btn_primary")
        self._btn_load.setFixedHeight(36)
        self._btn_load.clicked.connect(self._on_load_clicked)
        b_layout.addWidget(self._btn_load)

        self._btn_live = QPushButton("Start Live Feed")
        self._btn_live.setObjectName("btn_success")
        self._btn_live.setFixedHeight(36)
        self._btn_live.setCheckable(True)
        self._btn_live.clicked.connect(self._on_live_clicked)
        b_layout.addWidget(self._btn_live)

        # ── Progress ───────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.setFixedHeight(6)
        self._progress.setVisible(False)
        b_layout.addWidget(self._progress)

        # ── Status ─────────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size:11px; color:#8b949e;")
        b_layout.addWidget(self._status)

        b_layout.addStretch()
        layout.addWidget(body)

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
            self._btn_live.setObjectName("btn_danger")
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
        self._btn_live.setObjectName("btn_success")
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
            df = await data_feed.get_ohlcv(symbol, timeframe, limit=500)
            if df is None or df.empty:
                self._set_status(f"No data found for {symbol}.", error=True)
            else:
                self._set_status(
                    f"{symbol} [{timeframe}] — {len(df)} bars "
                    f"({df.index[0] if hasattr(df.index[0], 'date') else ''} …)"
                )
                self.data_loaded.emit(df, symbol, timeframe)
                # Apply MA visibility from checkboxes
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
