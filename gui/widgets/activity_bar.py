"""
gui/widgets/activity_bar.py
Barra di navigazione verticale 56px stile VS Code/Bloomberg.
Sei pulsanti icona per switch workspace — parte del layout root MainWindow.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QFrame,
    QPushButton,
    QVBoxLayout,
)

from gui.i18n import tr


# ─────────────────────────────────────────────────────────────────────────────
# Icone scelte: tutte disponibili in Segoe UI Symbol su Windows
# U+2316  POSITION INDICATOR  → Dashboard (griglia di punti ordinata)
# U+2197  NORTH EAST ARROW    → Order Ticket (operazione direzionale)
# U+25CB  WHITE CIRCLE        → Analysis (grafico/target)
# U+25A6  SQUARE WITH ORTHOGONAL CROSSHATCH FILL → Backtest
# U+2726  BLACK FOUR POINTED STAR → Patterns
# U+2699  GEAR                → Settings
# ─────────────────────────────────────────────────────────────────────────────

_WORKSPACE_DEFS = [
    (0, "⌖", "workspace.dashboard"),    # ⌖
    (1, "↗", "workspace.order_ticket"), # ↗
    (2, "○", "workspace.analysis"),     # ○
    (3, "▦", "workspace.backtest"),     # ▦
    (4, "✦", "workspace.patterns"),     # ✦
    (5, "⚙", "workspace.settings"),     # ⚙
]

_QSS_ACTIVITY_BAR = """
ActivityBar {
    background: #0d1117;
    border-right: 1px solid #30363d;
}

_ActivityButton {
    background: transparent;
    color: #a8b1bb;
    border: none;
    border-left: 3px solid transparent;
    font-family: "Segoe UI Symbol", "Segoe UI", sans-serif;
    font-size: 22px;
    padding: 0px;
    margin: 0px;
}

_ActivityButton:hover {
    background: #21262d;
    color: #c9d1d9;
}

_ActivityButton[active="true"] {
    background: #161b22;
    color: #58a6ff;
    border-left: 3px solid #58a6ff;
}
"""


class _ActivityButton(QPushButton):
    """Pulsante interno all'ActivityBar con gestione stato active tramite QSS property."""

    def __init__(self, icon_char: str, tooltip_key: str, parent=None):
        super().__init__(icon_char, parent)
        self.setFixedSize(56, 48)
        self.setToolTip(tr(tooltip_key))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setProperty("active", False)
        self.setObjectName(self.__class__.__name__)

    def set_active(self, active: bool) -> None:
        """Aggiorna la property QSS e forza il repaint dello stile."""
        if self.property("active") == active:
            return
        self.setProperty("active", active)
        # Necessario per far rileggere le regole QSS basate su property dinamica
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class ActivityBar(QFrame):
    """Barra verticale 56px con 6 pulsanti icona per switch workspace."""

    # Segnale emesso quando l'utente clicca un'icona
    workspace_changed = pyqtSignal(int)  # idx 0..5

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ActivityBar")
        self.setFixedWidth(56)

        # Applica QSS interno (non dipende dal foglio globale)
        self.setStyleSheet(_QSS_ACTIVITY_BAR)

        self._buttons: list[_ActivityButton] = []
        self._active_idx: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        for idx, icon_char, tooltip_key in _WORKSPACE_DEFS:
            btn = _ActivityButton(icon_char, tooltip_key, parent=self)
            btn.clicked.connect(self._make_click_handler(idx))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()

        # Stato iniziale: primo workspace attivo
        self._apply_active(0)

    # ─── API pubblica ──────────────────────────────────────────────────────

    def set_active(self, idx: int) -> None:
        """Evidenzia visivamente l'icona idx come attiva (chiamato da main_window per sync)."""
        if not (0 <= idx < len(self._buttons)):
            return
        self._apply_active(idx)

    # ─── Internals ────────────────────────────────────────────────────────

    def _apply_active(self, idx: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == idx)
        self._active_idx = idx

    def _make_click_handler(self, idx: int):
        """Factory closure — cattura idx per valore (evita il bug del for-loop)."""
        def _handler():
            self._apply_active(idx)
            self.workspace_changed.emit(idx)
        return _handler
