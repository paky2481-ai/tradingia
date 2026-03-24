"""
[Paky] Positions Panel — Posizioni live + Trading Manuale

Due sezioni:
  1. Tabella posizioni aperte (con P&L live, SL/TP, bottone Close)
  2. Form apertura manuale trade
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict

from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QTableWidgetItem, QHeaderView, QPushButton,
)
from PyQt6.QtGui import QColor

from core.signal_bus import (
    get_bus, PositionUpdateEvent, TradeOpenedEvent, TradeClosedEvent,
    OpenTradeCommand, CloseTradeCommand,
)

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
_STYLE_GRAY   = "color: #8b949e;"

_COL_DISPLAY = 0
_COL_DIR     = 1
_COL_QTY     = 2
_COL_ENTRY   = 3
_COL_CURRENT = 4
_COL_PNL     = 5
_COL_PNL_PCT = 6
_COL_SL      = 7
_COL_TP      = 8
_COL_CLOSE   = 9
_NCOLS       = 10


class PositionsPanel(QWidget):
    """Mostra posizioni aperte e permette apertura/chiusura manuale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._positions: Dict[str, dict] = {}   # symbol → row data

        uic.loadUi(str(_UI), self)

        # Ripristina i margini rimossi dal .ui per compatibilità PyQt6 uic
        self.posLayout.setContentsMargins(4, 6, 4, 4)
        self.manualLayout.setContentsMargins(8, 8, 8, 8)
        self.logLayout.setContentsMargins(6, 6, 6, 6)

        self._setup_table()
        self._setup_form()
        self._setup_connections()
        self._connect_bus()
        self._update_table_visibility()

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

    @pyqtSlot(object)
    def _on_trade_opened(self, ev: TradeOpenedEvent):
        """Aggiunge riga nella tabella posizioni."""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._positions[ev.symbol] = {"row": row}

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

        # Bottone close
        btn = QPushButton("Chiudi")
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
