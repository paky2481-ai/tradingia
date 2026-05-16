"""
PatternsWorkspace — workspace per il riconoscimento pattern real-time.

Layout: QSplitter orizzontale 2 pannelli
  Sinistra (35%)  PatternPanel — tabella pattern riconosciuti in real-time
  Destra   (65%)  ChartPanel   — placeholder per overlay pattern (Fase 5)

Il rendering del pattern overlay sul chart e' previsto in Fase 5.
Attualmente il ChartPanel funziona in modalita standalone senza overlay.
Il sync simbolo avviene via AppState.current_symbol.

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from gui.panels.chart_panel import ChartPanel
from gui.panels.pattern_panel import PatternPanel


class PatternsWorkspace(QWidget):
    """
    Workspace pattern recognition.

    Layout: QSplitter(H) → [PatternPanel 35%] [ChartPanel 65%]

    Pattern overlay sul chart: previsto in Fase 5 — attualmente placeholder.

    Uso in MainWindow (a cura di Paky):
        ws = PatternsWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PatternsWorkspace")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        root.addWidget(splitter)

        # Sinistra — pattern panel (35%)
        self._pattern_panel = PatternPanel()
        self._pattern_panel.setMinimumWidth(220)
        splitter.addWidget(self._pattern_panel)

        # Destra — chart panel (65%), placeholder per pattern overlay Fase 5
        self._chart_panel = ChartPanel()
        splitter.addWidget(self._chart_panel)

        # Ratio approssimati: 35% / 65%
        splitter.setSizes([350, 650])
        splitter.setStretchFactor(0, 0)   # pattern panel: relativamente fisso
        splitter.setStretchFactor(1, 1)   # chart: espandibile (pannello principale)
