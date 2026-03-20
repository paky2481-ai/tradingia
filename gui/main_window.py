"""
TradingIA Main Window
QMainWindow with dockable panels:
  - Left:   Watchlist
  - Center: Chart (main area)
  - Right:  Data panel
  - Bottom: Log / status
"""

from __future__ import annotations

import asyncio
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QLabel,
    QStatusBar, QToolBar, QApplication, QSizePolicy,
    QTextEdit, QVBoxLayout,
)

from gui.panels.chart_panel import ChartPanel
from gui.panels.watchlist_panel import WatchlistPanel
from gui.panels.data_panel import DataPanel
from gui.panels.ai_analysis_panel import AIAnalysisPanel


class LogPanel(QWidget):
    """Simple scrollable log panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(500)
        self._text.setStyleSheet(
            "background:#0d1117; color:#8b949e; "
            "font-family:monospace; font-size:12px; border:none;"
        )
        layout.addWidget(self._text)

    def append(self, msg: str, color: str = "#8b949e"):
        self._text.append(f'<span style="color:{color}">{msg}</span>')


class TradingMainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TradingIA")
        self.setMinimumSize(1280, 760)
        self.resize(1600, 960)

        self._setup_central()
        self._setup_docks()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        # Clock in status bar
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()

    # ── Central Widget ─────────────────────────────────────────────────────

    def _setup_central(self):
        self._chart_panel = ChartPanel()
        self._chart_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setCentralWidget(self._chart_panel)

    # ── Docks ──────────────────────────────────────────────────────────────

    def _setup_docks(self):
        # ── Watchlist (left) ──────────────────────────────────────────
        self._watchlist = WatchlistPanel()
        self._dock_watchlist = self._make_dock(
            "Watchlist", self._watchlist,
            Qt.DockWidgetArea.LeftDockWidgetArea,
            min_width=220, max_width=320,
        )

        # ── Data panel (right) ────────────────────────────────────────
        self._data_panel = DataPanel()
        self._dock_data = self._make_dock(
            "Data", self._data_panel,
            Qt.DockWidgetArea.RightDockWidgetArea,
            min_width=240, max_width=340,
        )

        # ── AI Analysis panel (right, below Data) ─────────────────────
        self._ai_panel = AIAnalysisPanel()
        self._dock_ai = self._make_dock(
            "AI Analysis", self._ai_panel,
            Qt.DockWidgetArea.RightDockWidgetArea,
            min_width=240, max_width=340,
        )
        # Tab AI Analysis with the Data dock
        self.tabifyDockWidget(self._dock_data, self._dock_ai)
        self._dock_data.raise_()   # Data tab visible by default

        # ── Log panel (bottom) ────────────────────────────────────────
        self._log_panel = LogPanel()
        self._dock_log = self._make_dock(
            "Log", self._log_panel,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            max_height=160,
        )
        self._dock_log.hide()   # hidden by default, toggle via menu

    def _make_dock(
        self,
        title: str,
        widget: QWidget,
        area: Qt.DockWidgetArea,
        min_width: int = 0,
        max_width: int = 0,
        max_height: int = 0,
    ) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable,
        )
        if min_width:
            dock.setMinimumWidth(min_width)
        if max_width:
            dock.setMaximumWidth(max_width)
        if max_height:
            dock.setMaximumHeight(max_height)
        self.addDockWidget(area, dock)
        return dock

    # ── Toolbar ────────────────────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        # Watchlist toggle
        act_wl = QAction("Watchlist", self)
        act_wl.setCheckable(True)
        act_wl.setChecked(True)
        act_wl.setToolTip("Toggle Watchlist panel")
        act_wl.toggled.connect(
            lambda v: self._dock_watchlist.setVisible(v)
        )
        tb.addAction(act_wl)

        # Data toggle
        act_data = QAction("Data", self)
        act_data.setCheckable(True)
        act_data.setChecked(True)
        act_data.setToolTip("Toggle Data panel")
        act_data.toggled.connect(
            lambda v: self._dock_data.setVisible(v)
        )
        tb.addAction(act_data)

        tb.addSeparator()

        # AI Analysis toggle
        act_ai = QAction("AI", self)
        act_ai.setCheckable(True)
        act_ai.setChecked(True)
        act_ai.setToolTip("Toggle AI Analysis panel")
        act_ai.toggled.connect(
            lambda v: self._dock_ai.setVisible(v)
        )
        tb.addAction(act_ai)

        # Log toggle
        act_log = QAction("Log", self)
        act_log.setCheckable(True)
        act_log.setChecked(False)
        act_log.setToolTip("Toggle Log panel")
        act_log.toggled.connect(
            lambda v: self._dock_log.setVisible(v)
        )
        tb.addAction(act_log)

        tb.addSeparator()

        # MA toggles
        for label, attr in [("MA20", "_act_ma20"), ("MA50", "_act_ma50"), ("MA200", "_act_ma200")]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(label != "MA200")
            act.toggled.connect(self._on_ma_toggled)
            setattr(self, attr, act)
            tb.addAction(act)

        tb.addSeparator()

        # Theme (placeholder for future light mode)
        act_theme = QAction("Dark", self)
        act_theme.setCheckable(True)
        act_theme.setChecked(True)
        act_theme.setToolTip("Toggle theme (Dark/Light)")
        tb.addAction(act_theme)

    def _on_ma_toggled(self):
        self._chart_panel.apply_ma_settings(
            ma20=self._act_ma20.isChecked(),
            ma50=self._act_ma50.isChecked(),
            ma200=self._act_ma200.isChecked(),
        )

    # ── Status Bar ─────────────────────────────────────────────────────────

    def _setup_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._lbl_status = QLabel("Ready")
        self._lbl_status.setContentsMargins(8, 0, 0, 0)
        sb.addWidget(self._lbl_status, 1)

        self._lbl_clock = QLabel("")
        self._lbl_clock.setContentsMargins(0, 0, 8, 0)
        sb.addPermanentWidget(self._lbl_clock)

        self._lbl_mode = QLabel("Paper Mode")
        self._lbl_mode.setStyleSheet(
            "background:#21262d; color:#8b949e; padding:2px 8px; "
            "border-radius:4px; font-size:11px;"
        )
        self._lbl_mode.setContentsMargins(0, 0, 8, 0)
        sb.addPermanentWidget(self._lbl_mode)

    def _update_clock(self):
        from datetime import datetime
        now = datetime.utcnow().strftime("UTC  %Y-%m-%d  %H:%M:%S")
        self._lbl_clock.setText(now)

    # ── Signal Connections ─────────────────────────────────────────────────

    def _connect_signals(self):
        # Watchlist row click → load chart
        self._watchlist.symbol_selected.connect(self._on_symbol_from_watchlist)

        # Data panel download complete → update chart
        self._data_panel.data_loaded.connect(self._on_data_loaded)

        # Data panel live tick → update chart
        self._data_panel.realtime_tick.connect(self._chart_panel.update_live_tick)

        # AI panel oscillator selection → update chart sub-panel
        self._ai_panel.oscillator_changed.connect(self._chart_panel.show_oscillator)

        # AI panel analysis complete → log result
        self._ai_panel.analysis_complete.connect(self._on_ai_analysis_complete)

    def _on_symbol_from_watchlist(self, symbol: str):
        """When user clicks a watchlist row, pre-fill data panel & load."""
        self._data_panel._symbol_input.setText(symbol)
        self._data_panel._on_load_clicked()
        self._log(f"Loading {symbol}…")

    def _on_data_loaded(self, df, symbol: str, timeframe: str):
        self._chart_panel.load_data(df, symbol, timeframe)
        ma = self._data_panel.ma_settings
        self._chart_panel.apply_ma_settings(**ma)
        self._lbl_status.setText(f"{symbol} [{timeframe}]  —  {len(df)} bars loaded")
        self._log(f"Loaded {symbol} [{timeframe}]: {len(df)} bars", color="#3fb950")

        # Forward data to AI Analysis panel
        from config.settings import settings
        asset_type = settings.asset_type_map.get(symbol, "stock")
        self._ai_panel.set_symbol(symbol, df, asset_type)

    def _on_ai_analysis_complete(self, result):
        regime = getattr(result, "regime", "?")
        hurst = getattr(result, "hurst", 0.0)
        strategy = getattr(result, "recommended_strategy", "?")
        self._log(
            f"AI [{result.symbol}] regime={regime} H={hurst:.3f} → {strategy}",
            color="#a371f7",
        )

    # ── Logging ────────────────────────────────────────────────────────────

    def _log(self, msg: str, color: str = "#8b949e"):
        self._log_panel.append(msg, color)
        self._lbl_status.setText(msg)
