"""
TradingIA Main Window — v3 Demo (gate review)

Layout:
    QVBoxLayout
    ├── TopBar (42px fissi)   — KPI live, clock UTC, bottone START/STOP
    └── QStackedWidget        — workspaces intercambiabili
        └── DashboardWorkspace  — MVP demo Bloomberg-style

AppState bridge:
    connect_signal_bus(get_bus()) collegato in __init__ → TopBar si aggiorna
    automaticamente quando l'engine vero emette eventi.
    In assenza di engine, il QTimer interno di DashboardWorkspace semina
    tick demo ogni 2s per dimostrare liveness.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QShortcut,
    QStatusBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.state.app_state import AppState
from gui.widgets.top_bar import TopBar
from gui.workspaces.dashboard import DashboardWorkspace
from core.signal_bus import get_bus


class TradingMainWindow(QMainWindow):
    """Finestra principale TradingIA — demo gate review."""

    def __init__(self) -> None:
        super().__init__()

        # Bridge SignalBus → AppState (noop se bus non ancora pronto)
        AppState.instance().connect_signal_bus(get_bus())

        self.setWindowTitle("TradingIA — Trading Terminal")
        self.setMinimumSize(1280, 760)
        self.resize(1680, 980)

        self._engine = None

        self._setup_layout()
        self._setup_statusbar()
        self._setup_shortcuts()

    # ── Layout centrale ───────────────────────────────────────────────────────

    def _setup_layout(self) -> None:
        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._top_bar = TopBar()
        v.addWidget(self._top_bar)

        self._stack = QStackedWidget()
        self._dashboard = DashboardWorkspace()
        self._stack.addWidget(self._dashboard)
        v.addWidget(self._stack, stretch=1)

        self.setCentralWidget(central)

    # ── Status bar minimale ───────────────────────────────────────────────────

    def _setup_statusbar(self) -> None:
        sb = QStatusBar()
        sb.showMessage("Pronto · Workspace: Dashboard")
        self.setStatusBar(sb)

    # ── Shortcut globali ──────────────────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        # F1 — aiuto
        f1 = QShortcut(QKeySequence("F1"), self)
        f1.activated.connect(self._show_help)

        # Ctrl+K — command palette (placeholder)
        ck = QShortcut(QKeySequence("Ctrl+K"), self)
        ck.activated.connect(self._show_command_palette)

        # F11 — fullscreen toggle
        f11 = QShortcut(QKeySequence("F11"), self)
        f11.activated.connect(self._toggle_fullscreen)

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            "TradingIA — Aiuto",
            "F1: questo aiuto.\n"
            "Premi ▶ START in alto per avviare il motore di trading.",
        )

    def _show_command_palette(self) -> None:
        QMessageBox.information(
            self,
            "Command palette",
            "Command palette · arriverà nelle prossime versioni",
        )

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ── Engine reference (chiamato da gui/app.py) ─────────────────────────────

    def set_engine(self, engine) -> None:
        """Salva il riferimento all'engine. AppState riceve gli eventi via SignalBus."""
        self._engine = engine
