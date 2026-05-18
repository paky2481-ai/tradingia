"""
AIObservatoryWorkspace — Osservatorio AI (Ctrl+3).

Separazione netta trader (frontend) vs AI (backend):
mostra lo stato del backend, i suoi log live e i segnali trovati.

Layout:
    QSplitter(V) root
    ├── QSplitter(H) top
    │   ├── _SymbolScanPanel  (~25%, 250px min)  — simboli in scan con LED
    │   └── _EventLogPanel    (~75%)             — log eventi colorati
    └── QSplitter(V) bottom
        ├── _SignalsTable                        — segnali AI trovati
        └── _PerformanceFooter (~60px)           — predizioni / hit rate

Segnali ascoltati:
    bus.qt.current_scan_symbol(symbol, loop_name) → LED pulse
    bus.qt.engine_status                          → log
    bus.qt.scan_result                            → log + tabella
    bus.qt.trend_alert                            → log

Interazione:
    Doppio click su riga tabella → AppState.current_symbol = symbol

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState
from gui.widgets.info.status_dot import StatusDot

# ── Palette ────────────────────────────────────────────────────────────────────
_BG_BASE      = "#0d1117"
_BG_SURFACE   = "#161b22"
_BG_ELEVATED  = "#21262d"
_BORDER       = "#30363d"
_BORDER_DIM   = "#21262d"
_TEXT         = "#e6edf3"
_MUTED        = "#a8b1bb"
_BULL         = "#3fb950"
_BEAR         = "#f85149"
_WARN         = "#d29922"
_ACCENT       = "#a371f7"
_INFO_LIGHT   = "#58a6ff"
_LOG_SCAN     = "#3fb950"   # verde — scan_result
_LOG_ALERT    = "#d29922"   # giallo — trend_alert
_LOG_START    = "#58a6ff"   # blu — scan_started / current_scan_symbol
_LOG_STATUS   = "#a8b1bb"   # grigio — engine_status

_UI_STACK     = '"Segoe UI", "Inter", "SF Pro Display", sans-serif'

# INSTRUMENTS in ordine canonico (da core.engine)
_INSTRUMENTS_ORDER = [
    ("EURUSD=X",  "EUR/USD"),
    ("GBPUSD=X",  "GBP/USD"),
    ("GC=F",      "XAU/USD"),
    ("^GSPC",     "S&P 500"),
    ("^GDAXI",    "DAX 40"),
    ("EURGBP=X",  "EUR/GBP"),
    ("JPY=X",     "USD/JPY"),
]

_MAX_LOG_ROWS = 200
_MAX_SIGNAL_ROWS = 500


def _section_label(text: str) -> QLabel:
    """Header sezione uppercase stile Bloomberg."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{_MUTED}; font-size:10px; font-weight:600;"
        f" font-family:{_UI_STACK}; text-transform:uppercase;"
        "  background:transparent; border:none; letter-spacing:0.4px;"
        "  padding:4px 6px 2px 6px;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lbl


def _panel_frame() -> QFrame:
    """Frame con sfondo surface e bordo sottile."""
    f = QFrame()
    f.setStyleSheet(
        f"background:{_BG_SURFACE}; border:1px solid {_BORDER}; border-radius:4px;"
    )
    f.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return f


# ═══════════════════════════════════════════════════════════════════════════════
# _SymbolScanPanel — lista simboli con LED
# ═══════════════════════════════════════════════════════════════════════════════

class _SymbolScanPanel(QWidget):
    """
    Lista dei simboli in scan con StatusDot LED + display + timestamp.
    Ascolta current_scan_symbol per fare pulse del LED corrispondente.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        outer.addWidget(_section_label(tr("observatory.symbols_in_scan")))

        # Scroll area per lista
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QWidget#SymbolList { background: transparent; }"
        )

        list_widget = QWidget()
        list_widget.setObjectName("SymbolList")
        list_widget.setStyleSheet(
            f"background:{_BG_SURFACE}; border:none;"
        )
        list_lay = QVBoxLayout(list_widget)
        list_lay.setContentsMargins(6, 4, 6, 4)
        list_lay.setSpacing(4)

        # Mappa symbol_yf → (StatusDot, timestamp_label)
        self._dots: dict[str, StatusDot] = {}
        self._ts_labels: dict[str, QLabel] = {}

        for sym_yf, display in _INSTRUMENTS_ORDER:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent; border:none;")
            row = QHBoxLayout(row_w)
            row.setContentsMargins(0, 2, 0, 2)
            row.setSpacing(6)

            dot = StatusDot()
            dot.set_state("idle")
            self._dots[sym_yf] = dot
            row.addWidget(dot)

            disp_lbl = QLabel(display)
            disp_lbl.setStyleSheet(
                f"color:{_TEXT}; font-size:11px; font-family:{_UI_STACK};"
                "  background:transparent; border:none;"
            )
            disp_lbl.setFixedWidth(60)
            row.addWidget(disp_lbl)

            ts_lbl = QLabel("")
            ts_lbl.setStyleSheet(
                f"color:{_MUTED}; font-size:9px; font-family:{_UI_STACK};"
                "  background:transparent; border:none;"
            )
            self._ts_labels[sym_yf] = ts_lbl
            row.addWidget(ts_lbl)
            row.addStretch(1)

            list_lay.addWidget(row_w)

        list_lay.addStretch(1)
        scroll.setWidget(list_widget)
        outer.addWidget(scroll, stretch=1)

        # Connetti segnale bus
        self._connect_bus()

    def _connect_bus(self) -> None:
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.qt.current_scan_symbol.connect(self._on_scan_symbol)
        except Exception:
            pass

    def _on_scan_symbol(self, symbol: str, loop_name: str) -> None:
        """Pulse LED del simbolo e aggiorna timestamp."""
        if symbol in self._dots:
            self._dots[symbol].pulse()
            now = datetime.utcnow().strftime("%H:%M:%S")
            self._ts_labels[symbol].setText(now)


# ═══════════════════════════════════════════════════════════════════════════════
# _EventLogPanel — log live eventi backend
# ═══════════════════════════════════════════════════════════════════════════════

class _EventLogPanel(QWidget):
    """
    Log testuale live eventi backend.
    Max 200 righe — FIFO. Auto-scroll all'aggiunta.
    Colori: verde=scan_result, giallo=trend_alert, blu=scan_started, grigio=status.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(_section_label(tr("observatory.log_events")))

        # Tabella log (1 colonna, no header)
        self._table = QTableWidget()
        self._table.setColumnCount(1)
        self._table.horizontalHeader().setVisible(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setStyleSheet(
            f"QTableWidget {{ background:{_BG_BASE}; border:none; color:{_TEXT}; }}"
            "QTableWidget::item { padding: 2px 6px; border:none; }"
            f"QTableWidget::item:selected {{ background:{_BG_ELEVATED}; }}"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background:{_BORDER}; border-radius:3px; }}"
        )
        fnt = QFont()
        fnt.setFamilies(["JetBrains Mono", "Consolas", "Courier New", "monospace"])
        fnt.setPixelSize(11)
        self._table.setFont(fnt)

        outer.addWidget(self._table, stretch=1)

        self._connect_bus()

    def _connect_bus(self) -> None:
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.qt.engine_status.connect(self._on_engine_status)
            bus.qt.scan_result.connect(self._on_scan_result)
            bus.qt.trend_alert.connect(self._on_trend_alert)
            bus.qt.current_scan_symbol.connect(self._on_scan_symbol)
        except Exception:
            pass

    def _append(self, text: str, color: str) -> None:
        """Aggiunge riga al log, rimuove la più vecchia se >200 righe."""
        row = self._table.rowCount()
        if row >= _MAX_LOG_ROWS:
            self._table.removeRow(0)
            row = self._table.rowCount()
        self._table.insertRow(row)
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._table.setItem(row, 0, item)
        self._table.setRowHeight(row, 18)
        self._table.scrollToBottom()

    def _ts(self) -> str:
        return datetime.utcnow().strftime("%H:%M:%S")

    def _on_scan_result(self, ev) -> None:
        sym = getattr(ev, "display", getattr(ev, "symbol", "?"))
        direction = getattr(ev, "direction", "")
        conf = getattr(ev, "confidence", 0.0)
        self._append(
            f"{self._ts()}  scan_result  {sym}  {direction}  conf={conf:.2f}",
            _LOG_SCAN,
        )

    def _on_trend_alert(self, ev) -> None:
        sym = getattr(ev, "display", getattr(ev, "symbol", "?"))
        atype = getattr(ev, "alert_type", "")
        self._append(
            f"{self._ts()}  trend_alert  {sym}  {atype}",
            _LOG_ALERT,
        )

    def _on_engine_status(self, ev) -> None:
        mode = getattr(ev, "mode", "")
        running = getattr(ev, "running", False)
        state_str = "RUNNING" if running else "STOPPED"
        self._append(
            f"{self._ts()}  engine_status  {state_str}  {mode}",
            _LOG_STATUS,
        )

    def _on_scan_symbol(self, symbol: str, loop_name: str) -> None:
        self._append(
            f"{self._ts()}  scan_started  {symbol}  [{loop_name}]",
            _LOG_START,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# _SignalsTable — tabella segnali AI trovati
# ═══════════════════════════════════════════════════════════════════════════════

class _SignalsTable(QWidget):
    """
    Tabella segnali AI trovati: TIME | SYMBOL | DIR | CONF | STRATEGY.
    Doppio click su riga → AppState.current_symbol = symbol.
    Listener: bus.qt.scan_result.
    """

    _COL_TIME     = 0
    _COL_SYMBOL   = 1
    _COL_DIR      = 2
    _COL_CONF     = 3
    _COL_STRATEGY = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(_section_label(tr("observatory.signals_table")))

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            tr("observatory.col_time"),
            tr("observatory.col_symbol"),
            tr("observatory.col_dir"),
            tr("observatory.col_conf"),
            tr("observatory.col_strategy"),
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setStyleSheet(
            f"QTableWidget {{ background:{_BG_BASE}; border:none; color:{_TEXT}; }}"
            "QTableWidget::item { padding: 2px 6px; border:none; }"
            f"QTableWidget::item:selected {{ background:{_BG_ELEVATED}; }}"
            f"QHeaderView::section {{ background:{_BG_ELEVATED}; color:{_MUTED};"
            f"  font-size:10px; padding:3px 6px; border:none;"
            f"  border-bottom:1px solid {_BORDER}; }}"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            f"QScrollBar::handle:vertical {{ background:{_BORDER}; border-radius:3px; }}"
        )

        # Larghezze colonne
        self._table.setColumnWidth(self._COL_TIME,     72)
        self._table.setColumnWidth(self._COL_SYMBOL,   80)
        self._table.setColumnWidth(self._COL_DIR,      50)
        self._table.setColumnWidth(self._COL_CONF,     50)

        self._table.cellDoubleClicked.connect(self._on_double_click)

        outer.addWidget(self._table, stretch=1)

        # Mappa row → symbol_yf per doppio click
        self._row_symbols: list[str] = []

        self._connect_bus()

    def _connect_bus(self) -> None:
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.qt.scan_result.connect(self._on_scan_result)
        except Exception:
            pass

    def _on_scan_result(self, ev) -> None:
        direction = getattr(ev, "direction", "none")
        if direction == "none":
            return  # non mostrare segnali neutri

        sym_yf   = getattr(ev, "symbol", "?")
        display  = getattr(ev, "display", sym_yf)
        conf     = getattr(ev, "confidence", 0.0)
        strategy = getattr(ev, "strategy", "")
        ts       = getattr(ev, "timestamp", None)
        time_str = ts.strftime("%H:%M:%S") if ts else datetime.utcnow().strftime("%H:%M:%S")

        row = self._table.rowCount()
        if row >= _MAX_SIGNAL_ROWS:
            self._table.removeRow(0)
            if self._row_symbols:
                self._row_symbols.pop(0)
            row = self._table.rowCount()

        self._table.insertRow(row)
        self._row_symbols.append(sym_yf)

        color = _BULL if direction in ("buy", "long") else _BEAR

        def _item(text: str, fg: str = _TEXT) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setForeground(QColor(fg))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            return item

        self._table.setItem(row, self._COL_TIME,     _item(time_str, _MUTED))
        self._table.setItem(row, self._COL_SYMBOL,   _item(display))
        self._table.setItem(row, self._COL_DIR,      _item(direction.upper(), color))
        self._table.setItem(row, self._COL_CONF,     _item(f"{conf:.2f}"))
        self._table.setItem(row, self._COL_STRATEGY, _item(strategy))
        self._table.setRowHeight(row, 20)
        self._table.scrollToBottom()

    def _on_double_click(self, row: int, _col: int) -> None:
        """Imposta AppState.current_symbol al simbolo della riga."""
        if 0 <= row < len(self._row_symbols):
            sym = self._row_symbols[row]
            try:
                AppState.instance().current_symbol = sym
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# _PerformanceFooter — footer placeholder metriche AI
# ═══════════════════════════════════════════════════════════════════════════════

class _PerformanceFooter(QWidget):
    """
    Footer compatto con metriche AI aggregate (placeholder — dati reali futura Fase).
    Mostra: Predizioni totali | Hit rate | Ultimi 50.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(40)
        self.setStyleSheet(
            f"background:{_BG_ELEVATED};"
            f"border-top:1px solid {_BORDER};"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(0)

        header = _section_label(tr("observatory.performance"))
        header.setStyleSheet(
            header.styleSheet() + "padding:0 8px 0 0;"
        )
        row.addWidget(header)

        self._pred_lbl = QLabel(tr("observatory.predictions", n=0))
        self._pred_lbl.setStyleSheet(self._val_style())
        row.addWidget(self._pred_lbl)

        row.addWidget(self._sep())

        self._hr_lbl = QLabel(tr("observatory.hit_rate_na"))
        self._hr_lbl.setStyleSheet(self._val_style())
        row.addWidget(self._hr_lbl)

        row.addWidget(self._sep())

        self._l50_lbl = QLabel(tr("observatory.last50_na"))
        self._l50_lbl.setStyleSheet(self._val_style())
        row.addWidget(self._l50_lbl)

        row.addStretch(1)

        # Contatore predizioni (incrementa a ogni scan_result con segnale)
        self._n_predictions = 0
        self._connect_bus()

    @staticmethod
    def _val_style() -> str:
        return (
            f"color:{_TEXT}; font-size:11px; font-family:{_UI_STACK};"
            "  background:transparent; border:none; padding-left:4px; padding-right:4px;"
        )

    @staticmethod
    def _sep() -> QLabel:
        lbl = QLabel("|")
        lbl.setStyleSheet(
            f"color:{_BORDER}; background:transparent; border:none; padding:0 6px;"
        )
        return lbl

    def _connect_bus(self) -> None:
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.qt.scan_result.connect(self._on_scan_result)
        except Exception:
            pass

    def _on_scan_result(self, ev) -> None:
        direction = getattr(ev, "direction", "none")
        if direction == "none":
            return
        self._n_predictions += 1
        self._pred_lbl.setText(tr("observatory.predictions", n=self._n_predictions))
        # Hit rate rimane "—" finché non collegato a store reale


# ═══════════════════════════════════════════════════════════════════════════════
# AIObservatoryWorkspace — root widget
# ═══════════════════════════════════════════════════════════════════════════════

class AIObservatoryWorkspace(QWidget):
    """
    Osservatorio AI — workspace Ctrl+3.

    Struttura:
        QVBoxLayout
        ├── (header label)
        └── QSplitter(V) main
            ├── QSplitter(H) top     (60% altezza)
            │   ├── _SymbolScanPanel  (25%, min 200px)
            │   └── _EventLogPanel    (75%)
            └── QSplitter(V) bottom  (40% altezza)
                ├── _SignalsTable
                └── _PerformanceFooter (40px fissi)

    Uso in MainWindow (a cura di Paky):
        ws = AIObservatoryWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AIObservatoryWorkspace")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background:{_BG_BASE};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Splitter principale V ─────────────────────────────────────────────
        v_main = QSplitter(Qt.Orientation.Vertical)
        v_main.setHandleWidth(2)
        v_main.setStyleSheet(
            f"QSplitter::handle {{ background:{_BORDER_DIM}; }}"
        )
        root.addWidget(v_main)

        # ── Top: simboli scan + log eventi ────────────────────────────────────
        h_top = QSplitter(Qt.Orientation.Horizontal)
        h_top.setHandleWidth(2)
        h_top.setStyleSheet(
            f"QSplitter::handle {{ background:{_BORDER_DIM}; }}"
        )

        self._symbol_panel = _SymbolScanPanel()
        h_top.addWidget(self._symbol_panel)

        self._log_panel = _EventLogPanel()
        h_top.addWidget(self._log_panel)

        h_top.setSizes([250, 750])
        h_top.setStretchFactor(0, 0)
        h_top.setStretchFactor(1, 1)
        v_main.addWidget(h_top)

        # ── Bottom: tabella segnali + footer ──────────────────────────────────
        v_bottom = QSplitter(Qt.Orientation.Vertical)
        v_bottom.setHandleWidth(2)
        v_bottom.setStyleSheet(
            f"QSplitter::handle {{ background:{_BORDER_DIM}; }}"
        )

        self._signals_table = _SignalsTable()
        v_bottom.addWidget(self._signals_table)

        self._perf_footer = _PerformanceFooter()
        v_bottom.addWidget(self._perf_footer)

        v_bottom.setSizes([300, 40])
        v_bottom.setStretchFactor(0, 1)
        v_bottom.setStretchFactor(1, 0)
        v_main.addWidget(v_bottom)

        # 60% top, 40% bottom
        v_main.setSizes([600, 400])
        v_main.setStretchFactor(0, 3)
        v_main.setStretchFactor(1, 2)

    # ── Accesso ai sotto-panel (per test) ──────────────────────────────────────

    @property
    def symbol_panel(self) -> _SymbolScanPanel:
        return self._symbol_panel

    @property
    def log_panel(self) -> _EventLogPanel:
        return self._log_panel

    @property
    def signals_table(self) -> _SignalsTable:
        return self._signals_table

    @property
    def dots(self) -> dict[str, StatusDot]:
        """Mappa symbol_yf → StatusDot per test LED."""
        return self._symbol_panel._dots
