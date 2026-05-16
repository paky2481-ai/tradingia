"""
AnalysisWorkspace — workspace per l'analisi tecnica + AI.

Layout: QSplitter(V)
  Top  (70%)  QSplitter(H)
    Sinistra (30%)  AIAnalysisPanel
    Centro   (70%)  ChartPanel
  Bottom (30%)  DataPanel (full width)

Tutti i panel sono istanziati localmente — il sync dati avviene via AppState/SignalBus.

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

from gui.panels.ai_analysis_panel import AIAnalysisPanel
from gui.panels.chart_panel import ChartPanel
from gui.panels.data_panel import DataPanel


class AnalysisWorkspace(QWidget):
    """
    Workspace analisi tecnica e AI.

    Layout:
        QSplitter(V)
        ├── QSplitter(H)
        │   ├── AIAnalysisPanel  (sinistra 30%)
        │   └── ChartPanel       (centro 70%)
        └── DataPanel            (bottom full width 30%)

    Uso in MainWindow (a cura di Paky):
        ws = AnalysisWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AnalysisWorkspace")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Splitter verticale esterno: top (chart+AI) vs bottom (data)
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(2)
        root.addWidget(v_splitter)

        # Splitter orizzontale top: AI (sinistra) + Chart (centro)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(2)

        self._ai_panel = AIAnalysisPanel()
        self._ai_panel.setMinimumWidth(220)
        h_splitter.addWidget(self._ai_panel)

        self._chart_panel = ChartPanel()
        h_splitter.addWidget(self._chart_panel)

        # Ratio H: 30% AI, 70% Chart
        h_splitter.setSizes([300, 700])
        h_splitter.setStretchFactor(0, 0)   # AI: relativamente fisso
        h_splitter.setStretchFactor(1, 1)   # Chart: espandibile

        v_splitter.addWidget(h_splitter)

        # Bottom: DataPanel full width
        self._data_panel = DataPanel()
        v_splitter.addWidget(self._data_panel)

        # Ratio V: 70% top, 30% bottom
        v_splitter.setSizes([700, 300])
        v_splitter.setStretchFactor(0, 1)   # top (chart area): espandibile
        v_splitter.setStretchFactor(1, 0)   # data panel: relativamente fisso
