"""
OrderTicketWorkspace — workspace "Operativo" (ex Ordini).

Layout: QSplitter(V) root
  Top (60%): QSplitter(H) → [PositionsPanel 50%] [EnginePanel 50%]
  Bottom (40%): QSplitter(H) → [form 320-380px] [tabella espandibile] [broker 380-450px]

Razionale: in alto STATO operativo (posizioni aperte, stato motore).
In basso AZIONI (nuovo ordine, storico, broker config).

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
from gui.panels.positions_panel import PositionsPanel
from gui.panels.engine_panel import EnginePanel


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
    # Altezza minima esplicita: evita overlap con widget sottostante
    # (text-transform+font-size:10px può collassare a 0 senza questo)
    lbl.setMinimumHeight(16)
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
        lay.setSpacing(8)

        # Symbol — Fase A.1 + D: QComboBox editable, popolato da INSTRUMENTS,
        # sync bidirezionale con AppState (inclusi simboli custom es. MSFT)
        lay.addWidget(_field_label(tr("order.field.symbol")))
        self._symbol_combo = QComboBox()
        self._symbol_combo.setEditable(True)
        self._symbol_combo.setMinimumHeight(28)
        self._populate_symbol_combo()
        lay.addWidget(self._symbol_combo)
        self._connect_symbol_state()

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
            "QPushButton#PrimaryButton:disabled {"
            "  background:#30363d; color:#6e7681;"
            "}"
        )
        lay.addWidget(self._submit_btn)

        # Fase 6 — collega stato motore: submit abilitato solo se engine running
        self._connect_engine_state()

    def _connect_engine_state(self) -> None:
        """Fase 6 — abilita/disabilita submit in base a AppState.engine_running."""
        try:
            from gui.state.app_state import AppState
            state = AppState.instance()
            state.engine_running_changed.connect(self._on_engine_state)
            self._on_engine_state(state.engine_running)
        except Exception:
            pass

    def _on_engine_state(self, running: bool) -> None:
        self._submit_btn.setEnabled(running)

    def _on_type_changed(self, order_type: str) -> None:
        """Mostra/nasconde il campo Price in base al tipo ordine."""
        show_price = order_type != "MARKET"
        self._price_label.setVisible(show_price)
        self._price_spin.setVisible(show_price)

    def _populate_symbol_combo(self) -> None:
        """Fase A.1 — popola il combo con INSTRUMENTS key/display."""
        try:
            from core.engine import INSTRUMENTS
            for symbol_yf, (display, *_) in INSTRUMENTS.items():
                self._symbol_combo.addItem(display, userData=symbol_yf)
        except Exception:
            # Fallback statico se engine non importabile (headless/test)
            self._symbol_combo.addItem("EUR/USD", userData="EURUSD=X")

    def _connect_symbol_state(self) -> None:
        """Fase A.1 + D — pre-seleziona AppState.current_symbol, ascolta i cambiamenti
        in entrambe le direzioni (AppState → combo e combo → AppState)."""
        try:
            from gui.state.app_state import AppState
            state = AppState.instance()
            self._sync_combo_to_symbol(state.current_symbol)
            # AppState → combo (simbolo cambiato da altra sorgente)
            state.current_symbol_changed.connect(self._sync_combo_to_symbol)
            # Combo → AppState (utente cambia manualmente il combo operativo)
            self._symbol_combo.currentTextChanged.connect(
                self._on_combo_text_changed
            )
        except Exception:
            pass

    def _on_combo_text_changed(self, text: str) -> None:
        """Fase D — reverse sync: combo Operativo → AppState.current_symbol."""
        if not text:
            return
        # Cerca se il testo corrisponde a un item INSTRUMENTS (userData = symbol_yf)
        for i in range(self._symbol_combo.count()):
            if self._symbol_combo.itemText(i) == text and self._symbol_combo.itemData(i):
                sym_yf = self._symbol_combo.itemData(i)
                break
        else:
            # Testo libero (es. "MSFT") — usalo direttamente come symbol_yf
            sym_yf = text.strip().upper()
        try:
            from gui.state.app_state import AppState
            state = AppState.instance()
            # Evita loop: aggiorna solo se diverso dal valore corrente
            if state.current_symbol != sym_yf:
                state.current_symbol = sym_yf
        except Exception:
            pass

    def _sync_combo_to_symbol(self, symbol_yf: str) -> None:
        """Fase A.1 + D — aggiorna la selezione del combo al simbolo passato.
        Se il simbolo non è in INSTRUMENTS lo imposta come testo libero (custom)."""
        # Blocca temporaneamente currentTextChanged per evitare loop
        try:
            self._symbol_combo.blockSignals(True)
            for i in range(self._symbol_combo.count()):
                if self._symbol_combo.itemData(i) == symbol_yf:
                    self._symbol_combo.setCurrentIndex(i)
                    return
            # Simbolo custom (es. MSFT) — imposta come editText
            self._symbol_combo.setEditText(symbol_yf)
        finally:
            self._symbol_combo.blockSignals(False)

    def current_symbol_yf(self) -> str:
        """Ritorna il symbol_yf selezionato nel combo."""
        data = self._symbol_combo.currentData()
        if data:
            return data
        # Combo editable — ritorna il testo libero
        return self._symbol_combo.currentText().strip().upper() or ""


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
    Workspace "Operativo" — stato operativo + gestione ordini.

    Layout:
        QSplitter(V) root
        ├── Top (60%):  QSplitter(H) → [PositionsPanel 50%] [EnginePanel 50%]
        └── Bottom (40%): QSplitter(H) → [form ~350px] [tabella] [broker ~450px]

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

        # ── Splitter verticale radice ─────────────────────────────────────
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(3)
        root.addWidget(v_splitter)

        # ── ZONA SUPERIORE: Posizioni + Engine (60% altezza) ─────────────
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.setHandleWidth(2)

        self._positions = PositionsPanel()
        top_splitter.addWidget(self._positions)

        self._engine = EnginePanel()
        top_splitter.addWidget(self._engine)

        top_splitter.setSizes([500, 500])
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)
        v_splitter.addWidget(top_splitter)

        # ── ZONA INFERIORE: Form + Tabella + Broker (40% altezza) ────────
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.setHandleWidth(2)

        # Sinistra — form ordine
        self._form_panel = _OrderFormPanel()
        self._form_panel.setMinimumWidth(320)
        self._form_panel.setMaximumWidth(400)
        bottom_splitter.addWidget(self._form_panel)

        # Centro — tabella ordini (espandibile)
        self._order_table = _OrderTablePanel()
        bottom_splitter.addWidget(self._order_table)

        # Destra — broker panel
        self._broker_panel = BrokerPanel()
        self._broker_panel.setMinimumWidth(380)
        self._broker_panel.setMaximumWidth(500)
        bottom_splitter.addWidget(self._broker_panel)

        bottom_splitter.setSizes([350, 700, 450])
        bottom_splitter.setStretchFactor(0, 0)   # form: relativamente fissa
        bottom_splitter.setStretchFactor(1, 1)   # tabella: espandibile
        bottom_splitter.setStretchFactor(2, 0)   # broker: relativamente fissa
        v_splitter.addWidget(bottom_splitter)

        # Ratio verticale: 60% top (stato) / 40% bottom (azioni)
        v_splitter.setSizes([600, 400])
        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 2)
