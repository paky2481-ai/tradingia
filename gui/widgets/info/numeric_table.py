"""
NumericTable — QTableWidget pre-configurato per dati finanziari.

Design:
  - Font monospace per le celle (Consolas/Cascadia)
  - Header uppercase, font 600, colore TEXT_MUTED
  - Griglia colore #21262d (BG_ELEVATED)
  - Selection full-row, sort abilitato
  - No zebra stripes
  - Supporto sparkline mini per colonna via Sparkline widget

Uso:
    table = NumericTable(["SYMBOL", "PRICE", "CHANGE", "VOLUME"])
    table.append_row({"SYMBOL": "AAPL", "PRICE": "182.43", "CHANGE": "+1.2%", "VOLUME": "45M"})
    table.set_row_color(0, "#3fb950")

    # Sostituisce la colonna indice 1 con sparkline mini
    table.add_sparkline_column(1, {0: [1,2,3,4,5], 1: [5,4,3,2,1]})
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


# ── Palette ───────────────────────────────────────────────────────────────────
_BG_BASE     = "#0d1117"
_BG_SURFACE  = "#161b22"
_BG_ELEVATED = "#21262d"
_BORDER      = "#30363d"
_TEXT        = "#e6edf3"
_TEXT_MUTED  = "#a8b1bb"


_QSS = """
QTableWidget {{
    background-color: {bg};
    color: {text};
    border: 1px solid {border};
    gridline-color: {elevated};
    outline: none;
    font-family: Consolas, 'Cascadia Code', 'JetBrains Mono', monospace;
    font-size: 11px;
}}
QTableWidget::item {{
    padding: 2px 6px;
    border: none;
}}
QTableWidget::item:selected {{
    background-color: #1f3058;
    color: {text};
}}
QHeaderView::section {{
    background-color: {surface};
    color: {muted};
    font-family: 'Segoe UI', Inter, sans-serif;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    padding: 3px 6px;
    border: none;
    border-bottom: 1px solid {border};
    border-right: 1px solid {elevated};
}}
QScrollBar:vertical {{
    background: {bg};
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {elevated};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
""".format(
    bg=_BG_BASE,
    surface=_BG_SURFACE,
    elevated=_BG_ELEVATED,
    border=_BORDER,
    text=_TEXT,
    muted=_TEXT_MUTED,
)


class NumericTable(QTableWidget):
    """
    QTableWidget pre-configurato Bloomberg-grade per dati finanziari.

    Parametri:
        columns    lista di stringhe — intestazioni colonne (uppercase automatico)
        parent     widget padre opzionale

    API:
        append_row(data: dict)
            Aggiunge una riga. Le chiavi devono corrispondere alle colonne.
            Chiavi non presenti in columns vengono ignorate.

        set_row_color(row_idx: int, color: str)
            Colora una riga (es. verde per profit).

        add_sparkline_column(col_idx: int, values_by_row: dict[int, list[float]])
            Sostituisce le cell di una colonna con mini Sparkline (80x22px).
            values_by_row mappa row_index → lista float.

    Uso:
        t = NumericTable(["SYMBOL", "PRICE", "CHANGE", "VOLUME"])
        t.append_row({"SYMBOL": "AAPL", "PRICE": "182.43", "CHANGE": "+1.2%", "VOLUME": "45M"})
        t.set_row_color(0, "#3fb950")
    """

    def __init__(
        self,
        columns: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(0, len(columns), parent)
        self._columns = [c.upper() for c in columns]
        self._col_index: dict[str, int] = {c: i for i, c in enumerate(self._columns)}

        self._setup_style()
        self._setup_headers()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _setup_style(self) -> None:
        self.setStyleSheet(_QSS)
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSortingEnabled(True)
        self.setShowGrid(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Stretch ultima colonna
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)

    def _setup_headers(self) -> None:
        self.setHorizontalHeaderLabels(self._columns)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def append_row(self, data: dict) -> None:
        """Aggiunge una riga al fondo della tabella."""
        row = self.rowCount()
        self.insertRow(row)
        for col_name, col_idx in self._col_index.items():
            value = str(data.get(col_name, ""))
            item = QTableWidgetItem(value)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                if self._is_numeric(value)
                else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self.setItem(row, col_idx, item)

    def set_row_color(self, row_idx: int, color: str) -> None:
        """Colora il foreground di tutti gli item di una riga."""
        if row_idx < 0 or row_idx >= self.rowCount():
            return
        qcol = QColor(color)
        for c in range(self.columnCount()):
            item = self.item(row_idx, c)
            if item is not None:
                item.setForeground(QBrush(qcol))

    def add_sparkline_column(
        self,
        col_idx: int,
        values_by_row: dict[int, list[float]],
    ) -> None:
        """
        Sostituisce le cell di col_idx con widget Sparkline mini.

        values_by_row: {row_index: [float, ...]}
        """
        from gui.widgets.info.sparkline import Sparkline

        if col_idx < 0 or col_idx >= self.columnCount():
            return

        for row_idx, values in values_by_row.items():
            if row_idx < 0 or row_idx >= self.rowCount():
                continue
            spark = Sparkline(width=80, height=20)
            spark.set_values(values)
            self.setCellWidget(row_idx, col_idx, spark)
            self.setRowHeight(row_idx, 24)

        # Imposta larghezza colonna sufficiente per sparkline
        self.setColumnWidth(col_idx, 86)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_numeric(value: str) -> bool:
        """True se il testo sembra numerico (per allineamento destra)."""
        s = value.strip().lstrip("+-").replace(",", "").replace(".", "", 1)
        return s.rstrip("%$€£¥").isdigit() or (
            len(s) > 0 and s[-1] in "MBKmsbk" and s[:-1].isdigit()
        )
