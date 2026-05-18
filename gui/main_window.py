"""
TradingIA Main Window — v5

Layout:
    QHBoxLayout (root)
    ├── ActivityBar (56px)    — navigazione verticale workspace
    └── QWidget (right_col)
        ├── TopBar (42px)     — KPI live, clock UTC, bottone START/STOP
        └── QStackedWidget    — 6 workspace intercambiabili

Workspace (indice 0..5):
    0 — DashboardWorkspace    (locale)
    1 — OrderTicketWorkspace  (Marco — import graceful con fallback)
    2 — AIObservatoryWorkspace (Marco — import graceful con fallback)
    3 — BacktestWorkspace     (Marco — import graceful con fallback)
    4 — PatternsWorkspace     (Marco — import graceful con fallback)
    5 — SettingsWorkspace     (locale)

Shortcut:
    Ctrl+1..6  — switch workspace
    F1         — aiuto
    Ctrl+K     — command palette (placeholder)
    F11        — fullscreen toggle

Persistenza QSettings:
    "active_workspace" (int)  — workspace attivo al close
    "window_geometry" (bytes) — size/position finestra
"""

from __future__ import annotations

from typing import Optional, Type

from PyQt6.QtCore import QByteArray, QSettings, QSize, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState
from gui.widgets.top_bar import TopBar
from gui.workspaces.dashboard import DashboardWorkspace
from gui.workspaces.settings import SettingsWorkspace
from core.signal_bus import get_bus

# ---------------------------------------------------------------------------
# Import graceful ActivityBar (Marco — creato in parallelo)
# ---------------------------------------------------------------------------

try:
    from gui.widgets.activity_bar import ActivityBar
    _HAS_ACTIVITY_BAR = True
except ImportError:
    _HAS_ACTIVITY_BAR = False

# ---------------------------------------------------------------------------
# Import graceful dei workspace di Marco
# ---------------------------------------------------------------------------

def _try_import_workspace(name: str) -> Optional[Type[QWidget]]:
    """
    Tenta l'import del workspace indicato.
    Ritorna la classe se disponibile, None altrimenti (fallback a placeholder).
    """
    try:
        if name == "order_ticket":
            from gui.workspaces.order_ticket import OrderTicketWorkspace
            return OrderTicketWorkspace
        if name == "analysis":
            # A.3: il workspace Analisi (Ctrl+3) è ora l'Osservatorio AI
            from gui.workspaces.ai_observatory import AIObservatoryWorkspace
            return AIObservatoryWorkspace
        if name == "backtest":
            from gui.workspaces.backtest import BacktestWorkspace
            return BacktestWorkspace
        if name == "patterns":
            from gui.workspaces.patterns import PatternsWorkspace
            return PatternsWorkspace
    except ImportError as exc:
        print(f"[main_window] Workspace '{name}' non ancora disponibile: {exc}")
    return None


def _make_placeholder(name: str) -> QWidget:
    """Widget placeholder per workspace non ancora implementati."""
    w = QWidget()
    w.setStyleSheet("background:#0d1117;")
    lbl = QLabel(f"Workspace '{name}'\nnon ancora disponibile")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("color:#a8b1bb; font-size:14px;")
    lay = QVBoxLayout(w)
    lay.addWidget(lbl)
    return w


# ---------------------------------------------------------------------------
# Definizione dei workspace nell'ordine canonico (indice 0..5)
# ---------------------------------------------------------------------------

_WORKSPACE_DEFS = [
    ("dashboard",    None),          # None = già importato sopra (DashboardWorkspace)
    ("order_ticket", None),          # Marco
    ("analysis",     None),          # Marco
    ("backtest",     None),          # Marco
    ("patterns",     None),          # Marco
    ("settings",     None),          # locale (SettingsWorkspace)
]

_WORKSPACE_NAMES = [name for name, _ in _WORKSPACE_DEFS]


# ---------------------------------------------------------------------------
# TradingMainWindow
# ---------------------------------------------------------------------------

class TradingMainWindow(QMainWindow):
    """Finestra principale TradingIA con 6 workspace switching."""

    def __init__(self) -> None:
        super().__init__()

        # Bridge SignalBus → AppState (noop se bus non ancora pronto)
        AppState.instance().connect_signal_bus(get_bus())

        self.setWindowTitle(tr("app.title"))
        self.setMinimumSize(1280, 760)

        self._engine = None

        self._setup_layout()
        self._setup_statusbar()
        self._setup_shortcuts()
        self._restore_state()

    # ── Layout centrale ───────────────────────────────────────────────────────

    def _setup_layout(self) -> None:
        central = QWidget()

        if _HAS_ACTIVITY_BAR:
            # ROOT: QHBoxLayout — ActivityBar | colonna destra
            root = QHBoxLayout(central)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # Sinistra: ActivityBar 56px fissi
            self._activity_bar = ActivityBar()
            self._activity_bar.workspace_changed.connect(self._switch_workspace)
            root.addWidget(self._activity_bar)

            # Destra: colonna verticale (TopBar + QStackedWidget)
            right_col = QWidget()
            v = QVBoxLayout(right_col)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)

            self._top_bar = TopBar()
            v.addWidget(self._top_bar)

            self._stack = QStackedWidget()
            self._stack.setContentsMargins(0, 0, 0, 0)
            v.addWidget(self._stack, stretch=1)

            root.addWidget(right_col, stretch=1)
        else:
            # FALLBACK: QVBoxLayout senza ActivityBar
            print("[main_window] ActivityBar non ancora disponibile")
            v = QVBoxLayout(central)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(0)

            self._top_bar = TopBar()
            v.addWidget(self._top_bar)

            self._stack = QStackedWidget()
            self._stack.setContentsMargins(0, 0, 0, 0)
            v.addWidget(self._stack, stretch=1)

        self.setCentralWidget(central)

        # Costruisce e aggiunge tutti i workspace nello stack
        self._workspaces: list[QWidget] = []
        self._build_workspaces()

    def _build_workspaces(self) -> None:
        """Costruisce i 6 workspace e li aggiunge allo stack."""
        for i, (name, _) in enumerate(_WORKSPACE_DEFS):
            widget = self._instantiate_workspace(name)
            self._workspaces.append(widget)
            self._stack.addWidget(widget)

    def _instantiate_workspace(self, name: str) -> QWidget:
        """Istanzia il workspace per nome con fallback a placeholder."""
        if name == "dashboard":
            return DashboardWorkspace()
        if name == "settings":
            return SettingsWorkspace()
        # Workspace di Marco — import graceful
        cls = _try_import_workspace(name)
        if cls is not None:
            try:
                return cls()
            except Exception as exc:
                print(f"[main_window] Errore istanziazione workspace '{name}': {exc}")
        return _make_placeholder(name)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _setup_statusbar(self) -> None:
        sb = QStatusBar()
        name_key = f"workspace.{_WORKSPACE_NAMES[0]}"
        sb.showMessage(tr("status.ready_workspace", workspace=tr(name_key)))
        self.setStatusBar(sb)

    # ── Shortcut globali ──────────────────────────────────────────────────────

    def _setup_shortcuts(self) -> None:
        # Ctrl+1..6 — switch workspace
        for i in range(len(_WORKSPACE_DEFS)):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            sc.activated.connect(lambda idx=i: self._switch_workspace(idx))

        # F1 — aiuto
        f1 = QShortcut(QKeySequence("F1"), self)
        f1.activated.connect(self._show_help)

        # Ctrl+K — command palette (placeholder)
        ck = QShortcut(QKeySequence("Ctrl+K"), self)
        ck.activated.connect(self._show_command_palette)

        # F11 — fullscreen toggle
        f11 = QShortcut(QKeySequence("F11"), self)
        f11.activated.connect(self._toggle_fullscreen)

    # ── Switch workspace ──────────────────────────────────────────────────────

    def _switch_workspace(self, idx: int) -> None:
        """Attiva il workspace all'indice dato e aggiorna statusbar e ActivityBar."""
        if not (0 <= idx < self._stack.count()):
            return
        self._stack.setCurrentIndex(idx)
        name_key = f"workspace.{_WORKSPACE_NAMES[idx]}"
        self.statusBar().showMessage(
            tr("status.ready_workspace", workspace=tr(name_key))
        )
        # Sync visivo ActivityBar (no-op se non disponibile)
        if _HAS_ACTIVITY_BAR and hasattr(self, "_activity_bar"):
            self._activity_bar.set_active(idx)

    # ── Azioni shortcut ───────────────────────────────────────────────────────

    def _show_help(self) -> None:
        QMessageBox.information(
            self,
            tr("help.f1.title"),
            tr("help.f1.body"),
        )

    def _show_command_palette(self) -> None:
        QMessageBox.information(
            self,
            tr("help.search.title"),
            tr("help.search.body"),
        )

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ── Persistenza stato ─────────────────────────────────────────────────────

    def _restore_state(self) -> None:
        """Ripristina geometria finestra e workspace attivo da QSettings."""
        qs = QSettings("TradingIA", "TradingIA")
        geom: QByteArray = qs.value("window_geometry", QByteArray())
        if geom and not geom.isEmpty():
            self.restoreGeometry(geom)
        else:
            self.resize(1680, 980)

        ws_idx = qs.value("active_workspace", 0, type=int)
        self._switch_workspace(ws_idx)

    def closeEvent(self, event) -> None:
        """Salva geometria e workspace attivo prima di chiudere."""
        qs = QSettings("TradingIA", "TradingIA")
        qs.setValue("window_geometry", self.saveGeometry())
        qs.setValue("active_workspace", self._stack.currentIndex())
        qs.sync()
        super().closeEvent(event)

    # ── Engine reference (chiamato da gui/app.py) ─────────────────────────────

    def set_engine(self, engine) -> None:
        """Salva il riferimento all'engine. AppState riceve gli eventi via SignalBus."""
        self._engine = engine
