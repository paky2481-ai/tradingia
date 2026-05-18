"""
[Paky] Positions Panel — Posizioni live + Trading Manuale

Due sezioni:
  1. Tabella posizioni aperte (con P&L live, SL/TP, bottone Close)
  2. Form apertura manuale trade

Fase 5.2: header P&L Totale grande + sparkline mini per ogni posizione.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, List

from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PyQt6.QtGui import QColor, QFont

from core.signal_bus import (
    get_bus, PositionUpdateEvent, TradeOpenedEvent, TradeClosedEvent,
    OpenTradeCommand, CloseTradeCommand,
)
from gui.i18n import tr
from gui.widgets.info import Sparkline, HelpIcon

_UI = Path(__file__).parent.parent / "ui" / "positions_panel.ui"

# Strumenti disponibili per trading manuale
MANUAL_SYMBOLS = [
    ("EUR/USD", "EURUSD=X"),
    ("GBP/USD", "GBPUSD=X"),
    ("XAU/USD", "XAUUSD=X"),
    ("S&P 500", "^GSPC"),
    ("DAX 40",  "^GDAXI"),
    ("EUR/GBP", "EURGBP=X"),
    ("USD/JPY", "JPY=X"),
]

_STYLE_GREEN  = "color: #3fb950; font-weight: bold;"
_STYLE_RED    = "color: #f85149; font-weight: bold;"
_STYLE_YELLOW = "color: #e3b341;"
_STYLE_GRAY   = "color: #a8b1bb;"

_COL_DISPLAY   = 0
_COL_DIR       = 1
_COL_QTY       = 2
_COL_ENTRY     = 3
_COL_CURRENT   = 4
_COL_PNL       = 5
_COL_PNL_PCT   = 6
_COL_SL        = 7
_COL_TP        = 8
_COL_MINI      = 9   # Fase 5.2 — Sparkline mini per riga
_COL_CLOSE     = 10
_NCOLS         = 11


class PositionsPanel(QWidget):
    """Mostra posizioni aperte e permette apertura/chiusura manuale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._positions: Dict[str, dict] = {}   # symbol → row data
        # Fase 5.2 — storico PnL per equity sparkline header
        self._pnl_history: List[float] = [0.0]
        # Fase 5.2 — storico prezzi per sparkline per riga
        self._price_history: Dict[str, List[float]] = {}  # symbol → lista prezzi
        # Fase 5.2 — sparkline widget per riga
        self._row_sparklines: Dict[str, Sparkline] = {}   # symbol → Sparkline
        # Totale PnL non realizzato corrente
        self._total_pnl: float = 0.0

        uic.loadUi(str(_UI), self)

        # Ripristina i margini rimossi dal .ui per compatibilità PyQt6 uic
        self.posLayout.setContentsMargins(4, 6, 4, 4)
        self.manualLayout.setContentsMargins(8, 8, 8, 8)
        self.logLayout.setContentsMargins(6, 6, 6, 6)

        self._build_pnl_header()
        self._setup_table()
        self._setup_form()
        self._setup_connections()
        self._connect_bus()
        self._connect_language_bus()
        self._update_table_visibility()

    # ─────────────────────────────────────────────────────────────────────
    # Fase 5.2 — Header P&L Totale
    # ─────────────────────────────────────────────────────────────────────

    def _build_pnl_header(self):
        """Inserisce header P&L Totale sopra posLayout nel layout genitore."""
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background:#161b22; border-bottom:1px solid #30363d; }"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 6, 10, 6)
        hl.setSpacing(12)

        # Label P&L grande
        lbl_cap = QLabel(tr("positions.total_pnl") + ":")
        lbl_cap.setStyleSheet("color:#a8b1bb; font-size:11px;")
        hl.addWidget(lbl_cap)

        self._lbl_total_pnl = QLabel("€ 0.00")
        self._lbl_total_pnl.setStyleSheet(
            "color:#e6edf3; font-size:16px; font-weight:bold; font-family:monospace;"
        )
        hl.addWidget(self._lbl_total_pnl)

        hl.addSpacing(12)

        # Sparkline equity curve mini (80x24)
        self._equity_sparkline = Sparkline(width=80, height=24)
        self._equity_sparkline.set_values([0.0])
        hl.addWidget(self._equity_sparkline)
        hl.addStretch()

        # HelpIcon
        self._help_icon = HelpIcon(tr("help.positions.title"), tr("help.positions.body"))
        hl.addWidget(self._help_icon)

        # Inserisco l'header all'inizio del layout principale del pannello
        try:
            main_layout = self.posLayout
            main_layout.insertWidget(0, header)
        except AttributeError:
            pass  # UI non ancora caricata — chiamato prima di uic.loadUi

    # ─────────────────────────────────────────────────────────────────────
    # Setup
    # ─────────────────────────────────────────────────────────────────────

    def _setup_table(self):
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_DISPLAY, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            self._table.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(self._table.EditTrigger.NoEditTriggers)

        self._trade_log.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._trade_log.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self._trade_log.verticalHeader().setVisible(False)
        self._trade_log.setEditTriggers(
            self._trade_log.EditTrigger.NoEditTriggers)

    def _setup_form(self):
        for display, _ in MANUAL_SYMBOLS:
            self._cmb_symbol.addItem(display)

    def _setup_connections(self):
        self._btn_buy.clicked.connect(lambda: self._on_manual_trade("buy"))
        self._btn_sell.clicked.connect(lambda: self._on_manual_trade("sell"))

    # ─────────────────────────────────────────────────────────────────────
    # Bus connections
    # ─────────────────────────────────────────────────────────────────────

    def _connect_language_bus(self):
        """Aggiorna HelpIcon al cambio lingua runtime."""
        try:
            get_bus().qt.language_changed.connect(lambda _: self._help_icon.update_texts(
                tr("help.positions.title"), tr("help.positions.body")
            ))
        except Exception:
            pass

    def _connect_bus(self):
        bus = get_bus()
        bus.qt.position_update.connect(self._on_position_update)
        bus.qt.trade_opened.connect(self._on_trade_opened)
        bus.qt.trade_closed.connect(self._on_trade_closed)

    # ─────────────────────────────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_position_update(self, ev: PositionUpdateEvent):
        """Aggiorna P&L live di una posizione aperta."""
        if ev.symbol not in self._positions:
            return

        row_idx = self._positions[ev.symbol]["row"]
        if row_idx >= self._table.rowCount():
            return

        self._set_cell(row_idx, _COL_CURRENT, f"{ev.current_price:.5f}")
        pnl_style = _STYLE_GREEN if ev.unrealized_pnl >= 0 else _STYLE_RED
        self._set_cell(row_idx, _COL_PNL, f"{ev.unrealized_pnl:+.2f}", pnl_style)
        self._set_cell(row_idx, _COL_PNL_PCT, f"{ev.pnl_pct:+.2f}%", pnl_style)

        # Fase 5.2 — aggiorna sparkline mini per riga
        spark = self._row_sparklines.get(ev.symbol)
        if spark is not None:
            hist = self._price_history.setdefault(ev.symbol, [ev.entry_price])
            hist.append(ev.current_price)
            if len(hist) > 20:
                hist[:] = hist[-20:]
            spark.set_values(hist)

        # Fase 5.2 — ricalcola totale PnL e aggiorna header
        self._recalculate_total_pnl(ev.symbol, ev.unrealized_pnl)

    def _recalculate_total_pnl(self, updated_symbol: str, new_pnl: float):
        """Aggiorna totale PnL e la sparkline equity curve nell'header."""
        try:
            self._positions[updated_symbol]["pnl"] = new_pnl
            total = sum(d.get("pnl", 0.0) for d in self._positions.values())
            self._total_pnl = total
            color = "#3fb950" if total >= 0 else "#f85149"
            self._lbl_total_pnl.setText(f"€ {total:+.2f}")
            self._lbl_total_pnl.setStyleSheet(
                f"color:{color}; font-size:16px; font-weight:bold; font-family:monospace;"
            )
            self._pnl_history.append(total)
            if len(self._pnl_history) > 50:
                self._pnl_history = self._pnl_history[-50:]
            self._equity_sparkline.set_values(self._pnl_history)
        except Exception:
            pass

    @pyqtSlot(object)
    def _on_trade_opened(self, ev: TradeOpenedEvent):
        """Aggiunge riga nella tabella posizioni."""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 34)
        self._positions[ev.symbol] = {"row": row, "pnl": 0.0}

        dir_style = _STYLE_GREEN if ev.direction == "buy" else _STYLE_RED
        dir_text  = "▲ BUY" if ev.direction == "buy" else "▼ SELL"

        self._set_cell(row, _COL_DISPLAY, ev.display)
        self._set_cell(row, _COL_DIR,     dir_text, dir_style)
        self._set_cell(row, _COL_QTY,     f"{ev.quantity:.4f}")
        self._set_cell(row, _COL_ENTRY,   f"{ev.entry_price:.5f}")
        self._set_cell(row, _COL_CURRENT, f"{ev.entry_price:.5f}")
        self._set_cell(row, _COL_PNL,     "0.00")
        self._set_cell(row, _COL_PNL_PCT, "0.00%")
        self._set_cell(row, _COL_SL,      f"{ev.stop_loss:.5f}", _STYLE_RED)
        self._set_cell(row, _COL_TP,      f"{ev.take_profit:.5f}", _STYLE_GREEN)

        # Fase 5.2 — Sparkline mini per riga (entry price come primo punto)
        spark = Sparkline(width=60, height=22)
        spark.set_values([ev.entry_price])
        self._price_history[ev.symbol] = [ev.entry_price]
        self._row_sparklines[ev.symbol] = spark
        self._table.setCellWidget(row, _COL_MINI, spark)
        self._table.setColumnWidth(_COL_MINI, 64)

        # Bottone close
        btn = QPushButton(tr("positions.btn_close"))
        btn.setFixedHeight(22)
        btn.setStyleSheet("""
            QPushButton {
                background: #30363d; color: #f85149;
                border-radius: 3px; font-size: 11px; padding: 0 6px;
            }
            QPushButton:hover { background: #6e271e; }
        """)
        symbol = ev.symbol
        btn.clicked.connect(lambda: self._close_position(symbol))
        self._table.setCellWidget(row, _COL_CLOSE, btn)

        self._update_table_visibility()

    @pyqtSlot(object)
    def _on_trade_closed(self, ev: TradeClosedEvent):
        """Rimuove dalla tabella e aggiunge al log."""
        if ev.symbol in self._positions:
            row = self._positions.pop(ev.symbol)["row"]
            self._table.removeRow(row)
            for sym, data in self._positions.items():
                if data["row"] > row:
                    data["row"] -= 1
            # Fase 5.2 — pulizia strutture per riga
            self._price_history.pop(ev.symbol, None)
            self._row_sparklines.pop(ev.symbol, None)

        # Aggiungi al log
        log_row = self._trade_log.rowCount()
        self._trade_log.insertRow(log_row)
        ts = ev.timestamp.strftime("%H:%M")
        pnl_style = _STYLE_GREEN if ev.pnl >= 0 else _STYLE_RED

        self._set_log_cell(log_row, 0, ts)
        self._set_log_cell(log_row, 1, ev.display)
        dir_text = "▲ BUY" if ev.direction == "buy" else "▼ SELL"
        dir_style = _STYLE_GREEN if ev.direction == "buy" else _STYLE_RED
        self._set_log_cell(log_row, 2, dir_text, dir_style)
        self._set_log_cell(log_row, 3, f"{ev.entry_price:.5f}")
        self._set_log_cell(log_row, 4, f"{ev.exit_price:.5f}")
        self._set_log_cell(log_row, 5, f"{ev.pnl:+.2f}", pnl_style)

        while self._trade_log.rowCount() > 50:
            self._trade_log.removeRow(0)

        self._update_table_visibility()

    # ─────────────────────────────────────────────────────────────────────
    # Azioni manuali
    # ─────────────────────────────────────────────────────────────────────

    def _on_manual_trade(self, direction: str):
        idx    = self._cmb_symbol.currentIndex()
        display, symbol = MANUAL_SYMBOLS[idx]
        qty    = self._spin_qty.value()
        sl     = self._spin_sl.value()
        tp     = self._spin_tp.value()

        cmd = OpenTradeCommand(
            symbol=symbol, direction=direction,
            quantity=qty, stop_loss=sl, take_profit=tp,
        )
        get_bus().send_command_sync(cmd)

    def _close_position(self, symbol: str):
        cmd = CloseTradeCommand(symbol=symbol)
        get_bus().send_command_sync(cmd)

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _set_cell(self, row: int, col: int, text: str, style: str = ""):
        item = QTableWidgetItem(text)
        if style:
            if "green" in style or "3fb950" in style:
                item.setForeground(QColor("#3fb950"))
            elif "red" in style or "f85149" in style:
                item.setForeground(QColor("#f85149"))
            elif "yellow" in style or "e3b341" in style:
                item.setForeground(QColor("#e3b341"))
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._table.setItem(row, col, item)

    def _set_log_cell(self, row: int, col: int, text: str, style: str = ""):
        item = QTableWidgetItem(text)
        if "3fb950" in style:
            item.setForeground(QColor("#3fb950"))
        elif "f85149" in style:
            item.setForeground(QColor("#f85149"))
        self._trade_log.setItem(row, col, item)

    def _update_table_visibility(self):
        has_positions = self._table.rowCount() > 0
        self._table.setVisible(has_positions)
        self._lbl_no_pos.setVisible(not has_positions)
