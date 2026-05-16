"""
BacktestWorkspace — workspace per il backtest strategia.

Layout: full width con padding 12px sui margini interni.
  BacktestPanel occupa tutto lo spazio disponibile.

Il padding interno evita che il panel si incolli ai bordi della finestra.

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from gui.panels.backtest_panel import BacktestPanel


class BacktestWorkspace(QWidget):
    """
    Workspace backtest — BacktestPanel espanso a tutto spazio disponibile.

    Padding di 12px sui 4 bordi per non incollare il panel ai bordi finestra.

    Uso in MainWindow (a cura di Paky):
        ws = BacktestWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BacktestWorkspace")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        self._backtest_panel = BacktestPanel()
        self._backtest_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._backtest_panel)
