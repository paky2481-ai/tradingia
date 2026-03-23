"""
TradingIA Main Window — v2 (Full Automated)

Layout docks:
  Left:    EnginePanel (status + controlli motore + trend alerts)
  Left 2:  WatchlistPanel (7 strumenti, quote live)
  Center:  ChartPanel (grafico live)
  Right:   AIAnalysisPanel / DataPanel (tab)
  Bottom:  PositionsPanel (posizioni live + trading manuale)
  Bottom2: LogPanel (log in tempo reale)
"""

from __future__ import annotations

import asyncio
from typing import Optional

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QLabel,
    QStatusBar, QToolBar, QApplication, QSizePolicy,
    QPlainTextEdit, QVBoxLayout, QPushButton, QHBoxLayout,
)

from gui.panels.chart_panel import ChartPanel
from gui.panels.watchlist_panel import WatchlistPanel
from gui.panels.data_panel import DataPanel
from gui.panels.ai_analysis_panel import AIAnalysisPanel
from gui.panels.engine_panel import EnginePanel
from gui.panels.positions_panel import PositionsPanel
from gui.panels.backtest_panel import BacktestPanel
from gui.panels.pattern_panel import PatternPanel
from core.signal_bus import get_bus


class LogPanel(QWidget):
    """Log panel in tempo reale con output colorato."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(1000)
        self._text.setStyleSheet(
            "background:#0d1117; color:#8b949e; "
            "font-family:monospace; font-size:11px; border:none;"
        )
        layout.addWidget(self._text)

    def append(self, msg: str, color: str = "#8b949e"):
        from datetime import datetime
        ts = datetime.utcnow().strftime("%H:%M:%S")
        self._text.appendHtml(f'<span style="color:#484f58">[{ts}]</span> <span style="color:{color}">{msg}</span>')
        self._text.ensureCursorVisible()


class TradingMainWindow(QMainWindow):
    """Finestra principale TradingIA v2."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TradingIA — Sistema Automatico")
        self.setMinimumSize(1400, 820)
        self.resize(1800, 1020)

        self._setup_central()
        self._setup_docks()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._connect_bus()

        # Clock UTC
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()

    # ─────────────────────────────────────────────────────────────────────
    # Central widget
    # ─────────────────────────────────────────────────────────────────────

    def _setup_central(self):
        self._chart_panel = ChartPanel()
        self._chart_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setCentralWidget(self._chart_panel)

    # ─────────────────────────────────────────────────────────────────────
    # Docks
    # ─────────────────────────────────────────────────────────────────────

    def _setup_docks(self):
        # ── Engine Panel (sinistra, sopra) ─────────────────────────────
        self._engine_panel = EnginePanel()
        self._dock_engine  = self._make_dock(
            "Engine", self._engine_panel,
            Qt.DockWidgetArea.LeftDockWidgetArea,
            min_width=230, max_width=320,
        )

        # ── Watchlist (sinistra, sotto l'engine) ───────────────────────
        self._watchlist   = WatchlistPanel()
        self._dock_watchlist = self._make_dock(
            "Watchlist", self._watchlist,
            Qt.DockWidgetArea.LeftDockWidgetArea,
            min_width=220, max_width=320,
        )

        # ── AI Analysis (destra) ────────────────────────────────────────
        self._ai_panel  = AIAnalysisPanel()
        self._dock_ai   = self._make_dock(
            "AI Analysis", self._ai_panel,
            Qt.DockWidgetArea.RightDockWidgetArea,
            min_width=260, max_width=360,
        )

        # ── Data Panel (destra, tabbed con AI) ─────────────────────────
        self._data_panel = DataPanel()
        self._dock_data  = self._make_dock(
            "Dati", self._data_panel,
            Qt.DockWidgetArea.RightDockWidgetArea,
            min_width=240, max_width=340,
        )
        self.tabifyDockWidget(self._dock_ai, self._dock_data)
        self._dock_ai.raise_()

        # ── Positions Panel (basso) ─────────────────────────────────────
        self._positions_panel = PositionsPanel()
        self._dock_positions  = self._make_dock(
            "Posizioni & Trading", self._positions_panel,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            max_height=360,
        )

        # ── Log (basso, tabbed con Positions) ──────────────────────────
        self._log_panel = LogPanel()
        self._dock_log  = self._make_dock(
            "Log", self._log_panel,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            max_height=360,
        )
        self.tabifyDockWidget(self._dock_positions, self._dock_log)

        # ── Backtest (basso, tabbed con Positions e Log) ────────────────
        self._backtest_panel = BacktestPanel()
        self._dock_backtest  = self._make_dock(
            "Backtest", self._backtest_panel,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            max_height=360,
        )
        self.tabifyDockWidget(self._dock_log, self._dock_backtest)

        # ── Pattern Observer (basso, tabbed con Positions/Log/Backtest) ─
        self._pattern_panel = PatternPanel()
        self._dock_pattern  = self._make_dock(
            "Patterns", self._pattern_panel,
            Qt.DockWidgetArea.BottomDockWidgetArea,
            max_height=360,
        )
        self.tabifyDockWidget(self._dock_backtest, self._dock_pattern)
        self._dock_positions.raise_()

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
        if min_width: dock.setMinimumWidth(min_width)
        if max_width: dock.setMaximumWidth(max_width)
        if max_height: dock.setMaximumHeight(max_height)
        self.addDockWidget(area, dock)
        return dock

    # ─────────────────────────────────────────────────────────────────────
    # Toolbar
    # ─────────────────────────────────────────────────────────────────────

    def _setup_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        panels = [
            ("Engine",    "_dock_engine",    True),
            ("Watchlist", "_dock_watchlist", True),
            ("AI",        "_dock_ai",        True),
            ("Dati",      "_dock_data",      True),
            ("Posizioni", "_dock_positions", True),
            ("Log",       "_dock_log",       False),
            ("Backtest",  "_dock_backtest",  False),
            ("Patterns",  "_dock_pattern",   True),
        ]
        for label, attr, default in panels:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(default)
            dock_attr = attr
            act.toggled.connect(lambda v, a=dock_attr: getattr(self, a).setVisible(v))
            tb.addAction(act)

        tb.addSeparator()

        for label, attr in [("MA20", "_act_ma20"), ("MA50", "_act_ma50"), ("MA200", "_act_ma200")]:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(label != "MA200")
            act.toggled.connect(self._on_ma_toggled)
            setattr(self, attr, act)
            tb.addAction(act)

    def _on_ma_toggled(self):
        self._chart_panel.apply_ma_settings(
            ma20=self._act_ma20.isChecked(),
            ma50=self._act_ma50.isChecked(),
            ma200=self._act_ma200.isChecked(),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Status bar
    # ─────────────────────────────────────────────────────────────────────

    def _setup_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)

        self._lbl_status = QLabel("Pronto")
        self._lbl_status.setContentsMargins(8, 0, 0, 0)
        sb.addWidget(self._lbl_status, 1)

        self._lbl_equity_sb = QLabel("Equity: —")
        self._lbl_equity_sb.setStyleSheet(
            "background:#21262d; color:#e6edf3; padding:2px 8px; "
            "border-radius:4px; font-size:11px; font-weight:bold;"
        )
        sb.addPermanentWidget(self._lbl_equity_sb)

        self._lbl_pnl_sb = QLabel("P&L: —")
        self._lbl_pnl_sb.setStyleSheet(
            "background:#21262d; color:#8b949e; padding:2px 8px; "
            "border-radius:4px; font-size:11px;"
        )
        sb.addPermanentWidget(self._lbl_pnl_sb)

        self._lbl_engine_sb = QLabel("● Engine: FERMO")
        self._lbl_engine_sb.setStyleSheet(
            "background:#21262d; color:#8b949e; padding:2px 8px; "
            "border-radius:4px; font-size:11px;"
        )
        sb.addPermanentWidget(self._lbl_engine_sb)

        self._lbl_clock = QLabel("")
        self._lbl_clock.setContentsMargins(0, 0, 8, 0)
        sb.addPermanentWidget(self._lbl_clock)

    def _update_clock(self):
        from datetime import datetime
        now = datetime.utcnow().strftime("UTC  %Y-%m-%d  %H:%M:%S")
        self._lbl_clock.setText(now)

    # ─────────────────────────────────────────────────────────────────────
    # Connections (GUI panels tra loro)
    # ─────────────────────────────────────────────────────────────────────

    def _connect_signals(self):
        self._watchlist.symbol_selected.connect(self._on_symbol_from_watchlist)
        self._data_panel.data_loaded.connect(self._on_data_loaded)
        self._data_panel.realtime_tick.connect(self._chart_panel.update_live_tick)
        self._ai_panel.oscillator_changed.connect(self._chart_panel.show_oscillator)
        self._ai_panel.analysis_complete.connect(self._on_ai_complete)

    def _on_symbol_from_watchlist(self, symbol: str):
        self._data_panel._symbol_input.setText(symbol)
        self._data_panel._on_load_clicked()

    def _on_data_loaded(self, df, symbol: str, timeframe: str):
        self._chart_panel.load_data(df, symbol, timeframe)
        ma = self._data_panel.ma_settings
        self._chart_panel.apply_ma_settings(**ma)
        self._lbl_status.setText(f"{symbol} [{timeframe}] — {len(df)} barre")
        self._log(f"Caricato {symbol} [{timeframe}]: {len(df)} barre", "#3fb950")
        from config.settings import settings
        asset_type = settings.asset_type_map.get(symbol, "stock")
        self._ai_panel.set_symbol(symbol, df, asset_type)

    def _on_ai_complete(self, result):
        regime   = getattr(result, "regime", "?")
        hurst    = getattr(result, "hurst", 0.0)
        strategy = getattr(result, "recommended_strategy", "?")
        self._log(
            f"AI [{result.symbol}] regime={regime} H={hurst:.3f} → {strategy}", "#a371f7"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Bus connections (Engine → GUI)
    # ─────────────────────────────────────────────────────────────────────

    def _connect_bus(self):
        bus = get_bus()
        bus.qt.engine_started.connect(self._on_engine_started)
        bus.qt.engine_stopped.connect(self._on_engine_stopped)
        bus.qt.engine_status.connect(self._on_engine_status)
        bus.qt.log_message.connect(self._log)

    def _on_engine_started(self):
        self._lbl_engine_sb.setText("● Engine: ATTIVO")
        self._lbl_engine_sb.setStyleSheet(
            "background:#1a7f37; color:white; padding:2px 8px; "
            "border-radius:4px; font-size:11px; font-weight:bold;"
        )
        self._dock_log.show()

    def _on_engine_stopped(self):
        self._lbl_engine_sb.setText("● Engine: FERMO")
        self._lbl_engine_sb.setStyleSheet(
            "background:#21262d; color:#8b949e; padding:2px 8px; "
            "border-radius:4px; font-size:11px;"
        )

    def _on_engine_status(self, ev):
        self._lbl_equity_sb.setText(f"Equity: €{ev.equity:,.2f}")
        pnl_color = "#3fb950" if ev.daily_pnl >= 0 else "#f85149"
        self._lbl_pnl_sb.setText(f"P&L: €{ev.daily_pnl:+.2f}")
        self._lbl_pnl_sb.setStyleSheet(
            f"background:#21262d; color:{pnl_color}; padding:2px 8px; "
            "border-radius:4px; font-size:11px; font-weight:bold;"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Log
    # ─────────────────────────────────────────────────────────────────────

    def _log(self, msg: str, color: str = "#8b949e"):
        self._log_panel.append(msg, color)
        # Status bar: mostra solo messaggi non grigi (importanti)
        if color not in ("#8b949e", "#484f58"):
            self._lbl_status.setText(msg[:80])

    # ─────────────────────────────────────────────────────────────────────
    # Engine reference (impostato da app.py)
    # ─────────────────────────────────────────────────────────────────────

    def set_engine(self, engine):
        self._engine_panel.set_engine(engine)
