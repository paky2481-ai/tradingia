"""
OrderTicketWorkspace — workspace per la gestione ordini.

Layout: QSplitter orizzontale 3 pannelli
  Sinistra (30%)  Form nuovo ordine con campi SL/TP, risk info inline
  Centro  (45%)   Tabella ordini attivi/storici (QTableWidget 8 col)
  Destra  (25%)   BrokerPanel istanziato localmente

I dati di risk (capitale a rischio, R:R, Kelly) sono placeholder statici.
Il sync reale arriva via AppState/SignalBus — non gestito in questo workspace.

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.panels.broker_panel import BrokerPanel


# ── Palette (coerente con dark.qss e dashboard.py) ───────────────────────────
_BG_SURFACE  = "#161b22"
_BG_ELEVATED = "#21262d"
_BORDER      = "#30363d"
_TEXT        = "#e6edf3"
_MUTED       = "#a8b1bb"
_BULL        = "#3fb950"
_BEAR        = "#f85149"
_WARN        = "#d29922"
_ACCENT      = "#a371f7"

_UI_STACK    = '"Segoe UI", "Inter", "SF Pro Display", sans-serif'
_MONO_STACK  = '"Consolas", "Cascadia Code", "JetBrains Mono", monospace'

# Demo data per la tabella ordini (TIME, SYM, DIR, TYPE, QTY, PRICE, STATUS, PNL)
_DEMO_ORDERS = [
    ("09:31:02", "EUR/USD",  "BUY",  "MARKET", "10000", "1.0872", "FILLED",  "+€ 45.20"),
    ("09:28:47", "XAU/USD",  "SELL", "LIMIT",  "1",     "2360.00","PENDING", "—"),
    ("09:15:33", "GBP/USD",  "BUY",  "STOP",   "5000",  "1.2680", "FILLED",  "+€ 102.50"),
    ("08:55:10", "S&P 500",  "SELL", "MARKET", "1",     "5275.00","FILLED",  "-€ 33.10"),
    ("08:30:00", "DAX",      "BUY",  "LIMIT",  "1",     "18700.0","CANCELLED","—"),
]


def _field_label(text: str) -> QLabel:
    """Label campo form — muted, uppercase, 10px."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{_MUTED}; font-size:10px; font-weight:600;"
        f" font-family:{_UI_STACK}; text-transform:uppercase;"
        "  background:transparent; border:none; letter-spacing:0.4px;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lbl


def _risk_row(label: str, value: str) -> QWidget:
    """Riga risk info: [label muted] [valore a destra]."""
    row = QWidget()
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color:{_MUTED}; font-size:10px; font-family:{_UI_STACK};"
        "  background:transparent; border:none;"
    )
    val = QLabel(value)
    val.setStyleSheet(
        f"color:{_TEXT}; font-size:10px; font-family:{_MONO_STACK}; font-weight:600;"
        "  background:transparent; border:none;"
    )
    val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    lay.addWidget(lbl)
    lay.addStretch(1)
    lay.addWidget(val)
    return row


def _hsep() -> QFrame:
    """Separatore orizzontale 1px."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background:{_BORDER}; border:none;")
    sep.setFixedHeight(1)
    return sep


# ═══════════════════════════════════════════════════════════════════════════
# Form ordine — pannello sinistro
# ═══════════════════════════════════════════════════════════════════════════

class _OrderFormPanel(QGroupBox):
    """
    Form per l'inserimento di un nuovo ordine.

    Campi: symbol, direction, quantity, order type, price (condizionale),
    SL, TP, risk info inline (placeholder).
    Il campo Price e' visibile solo se il tipo non e' MARKET.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("order.group_title"), parent)
        self.setObjectName("OrderFormPanel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 18, 10, 10)
        lay.setSpacing(6)

        # Symbol
        lay.addWidget(_field_label(tr("order.field.symbol")))
        self._symbol_edit = QLineEdit()
        self._symbol_edit.setPlaceholderText(tr("order.placeholder.symbol"))
        self._symbol_edit.setMinimumHeight(28)
        lay.addWidget(self._symbol_edit)

        # Direction
        lay.addWidget(_field_label(tr("order.field.direction")))
        self._direction_combo = QComboBox()
        self._direction_combo.addItems(["BUY", "SELL"])
        self._direction_combo.setMinimumHeight(28)
        lay.addWidget(self._direction_combo)

        # Quantity
        lay.addWidget(_field_label(tr("order.field.quantity")))
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 1_000_000)
        self._qty_spin.setValue(1000)
        self._qty_spin.setSingleStep(100)
        self._qty_spin.setMinimumHeight(28)
        lay.addWidget(self._qty_spin)

        # Order type
        lay.addWidget(_field_label(tr("order.field.type")))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["MARKET", "LIMIT", "STOP", "STOP-LIMIT"])
        self._type_combo.setMinimumHeight(28)
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        lay.addWidget(self._type_combo)

        # Price — visibile solo se non MARKET
        self._price_label = _field_label(tr("order.field.price"))
        lay.addWidget(self._price_label)
        self._price_spin = QDoubleSpinBox()
        self._price_spin.setRange(0.0, 9_999_999.0)
        self._price_spin.setDecimals(4)
        self._price_spin.setValue(1.0872)
        self._price_spin.setMinimumHeight(28)
        lay.addWidget(self._price_spin)
        # MARKET selezionato di default → nascondi price
        self._price_label.setVisible(False)
        self._price_spin.setVisible(False)

        lay.addWidget(_hsep())

        # Stop Loss
        lay.addWidget(_field_label(tr("order.sl_label")))
        self._sl_spin = QDoubleSpinBox()
        self._sl_spin.setRange(0.0, 9_999_999.0)
        self._sl_spin.setDecimals(4)
        self._sl_spin.setValue(0.0)
        self._sl_spin.setMinimumHeight(28)
        lay.addWidget(self._sl_spin)

        # Take Profit
        lay.addWidget(_field_label(tr("order.tp_label")))
        self._tp_spin = QDoubleSpinBox()
        self._tp_spin.setRange(0.0, 9_999_999.0)
        self._tp_spin.setDecimals(4)
        self._tp_spin.setValue(0.0)
        self._tp_spin.setMinimumHeight(28)
        lay.addWidget(self._tp_spin)

        lay.addWidget(_hsep())

        # Risk info inline (placeholder — calcoli reali via AppState/engine)
        lay.addWidget(_risk_row(tr("order.risk_capital"), "—  %"))
        lay.addWidget(_risk_row(tr("order.risk_rr"), "—  :  1"))
        lay.addWidget(_risk_row(tr("order.risk_kelly"), "—  %"))

        lay.addStretch(1)

        # Bottone submit primario
        self._submit_btn = QPushButton(tr("order.btn_submit"))
        self._submit_btn.setObjectName("PrimaryButton")
        self._submit_btn.setMinimumHeight(36)
        self._submit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_btn.setStyleSheet(
            "QPushButton#PrimaryButton {"
            f"  background:{_ACCENT}; color:#fff;"
            "  border:none; border-radius:4px;"
            "  font-size:12px; font-weight:700; letter-spacing:0.5px;"
            "}"
            "QPushButton#PrimaryButton:hover {"
            "  background:#b694f8;"
            "}"
            "QPushButton#PrimaryButton:pressed {"
            "  background:#8c55f5;"
            "}"
        )
        lay.addWidget(self._submit_btn)

    def _on_type_changed(self, order_type: str) -> None:
        """Mostra/nasconde il campo Price in base al tipo ordine."""
        show_price = order_type != "MARKET"
        self._price_label.setVisible(show_price)
        self._price_spin.setVisible(show_price)


# ═══════════════════════════════════════════════════════════════════════════
# Tabella ordini — pannello centrale
# ═══════════════════════════════════════════════════════════════════════════

class _OrderTablePanel(QWidget):
    """
    Tabella 8 colonne con demo data 5 righe.
    Header: TIME / SYMBOL / DIR / TYPE / QTY / PRICE / STATUS / PNL
    """

    _COLUMNS = 8

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OrderTablePanel")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._table = QTableWidget(len(_DEMO_ORDERS), self._COLUMNS, self)
        self._table.setObjectName("OrderTable")
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Header
        headers = [
            tr("order.header.time"),
            tr("order.header.symbol"),
            tr("order.header.direction"),
            tr("order.header.type"),
            tr("order.header.quantity"),
            tr("order.header.price"),
            tr("order.header.status"),
            tr("order.header.pnl"),
        ]
        self._table.setHorizontalHeaderLabels(headers)

        # Stile tabella
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)

        # A.2 — Resize automatico colonne: ResizeToContents per tutte, Stretch
        # per l'ultima (P&L) così non rimane spazio vuoto a destra.
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(
            self._COLUMNS - 1, QHeaderView.ResizeMode.Stretch
        )

        # Popola demo data
        self._populate_demo()

        lay.addWidget(self._table)

    def _populate_demo(self) -> None:
        """Inserisce le 5 righe demo con colorazione stato."""
        for row_idx, order in enumerate(_DEMO_ORDERS):
            for col_idx, cell_value in enumerate(order):
                item = QTableWidgetItem(cell_value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                )
                # Colorazione direzionale
                if col_idx == 2:  # DIR
                    color = _BULL if cell_value == "BUY" else _BEAR
                    item.setForeground(QColor(color))
                # Colorazione stato
                elif col_idx == 6:  # STATUS
                    status_colors = {
                        "FILLED": _BULL,
                        "PENDING": _WARN,
                        "CANCELLED": _MUTED,
                    }
                    c = status_colors.get(cell_value, _TEXT)
                    item.setForeground(QColor(c))
                # Colorazione P&L
                elif col_idx == 7:  # PNL
                    if cell_value.startswith("+"):
                        item.setForeground(QColor(_BULL))
                    elif cell_value.startswith("-"):
                        item.setForeground(QColor(_BEAR))

                self._table.setItem(row_idx, col_idx, item)

        # Colonna widths ragionevoli
        col_widths = [70, 80, 45, 80, 60, 70, 70, 80]
        for i, w in enumerate(col_widths):
            self._table.setColumnWidth(i, w)


# ═══════════════════════════════════════════════════════════════════════════
# OrderTicketWorkspace — root widget
# ═══════════════════════════════════════════════════════════════════════════

class OrderTicketWorkspace(QWidget):
    """
    Workspace per creazione e gestione ordini.

    Layout: QSplitter(H) → [form 30%] [tabella 45%] [broker panel 25%]

    Uso in MainWindow (a cura di Paky):
        ws = OrderTicketWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OrderTicketWorkspace")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        root.addWidget(splitter)

        # Sinistra — form ordine (30%)
        self._form_panel = _OrderFormPanel()
        self._form_panel.setMinimumWidth(330)
        splitter.addWidget(self._form_panel)

        # Centro — tabella ordini (45%)
        self._order_table = _OrderTablePanel()
        splitter.addWidget(self._order_table)

        # Destra — broker panel (25%)
        self._broker_panel = BrokerPanel()
        self._broker_panel.setMinimumWidth(420)
        splitter.addWidget(self._broker_panel)

        # Ratio approssimati: 22 / 47 / 31
        splitter.setSizes([350, 750, 480])
        splitter.setStretchFactor(0, 0)   # form: dimensione relativamente fissa
        splitter.setStretchFactor(1, 1)   # tabella: espandibile
        splitter.setStretchFactor(2, 0)   # broker: relativamente fisso
