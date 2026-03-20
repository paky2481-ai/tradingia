"""
Watchlist Panel
Real-time quote table with color-coded price changes.
Emits symbol_selected(symbol) signal when user clicks a row.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QPushButton, QAbstractItemView,
)


# Default watchlists
DEFAULT_WATCHLISTS: Dict[str, List[str]] = {
    "Stocks": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "SPY"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"],
    "Forex":  ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"],
    "Indices": ["^GSPC", "^DJI", "^IXIC", "^FTSE"],
}

COLS = ["Symbol", "Price", "Change", "Change%", "Volume"]
COL_SYMBOL  = 0
COL_PRICE   = 1
COL_CHANGE  = 2
COL_CHANGEP = 3
COL_VOLUME  = 4

C_GREEN = QColor("#3fb950")
C_RED   = QColor("#f85149")
C_MUTED = QColor("#8b949e")


def _fmt_volume(v) -> str:
    if v is None:
        return "--"
    v = float(v)
    if v >= 1e9:
        return f"{v/1e9:.1f}B"
    if v >= 1e6:
        return f"{v/1e6:.1f}M"
    if v >= 1e3:
        return f"{v/1e3:.1f}K"
    return str(int(v))


def _item(text: str, align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setTextAlignment(align)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return it


class WatchlistPanel(QWidget):
    """Watchlist panel with auto-refreshing quotes."""

    symbol_selected = pyqtSignal(str)   # emitted when user clicks a row

    def __init__(self, parent=None):
        super().__init__(parent)
        self._quotes: Dict[str, Dict] = {}
        self._symbols: List[str] = []
        self._active_list = "Stocks"
        self._refresh_task: Optional[asyncio.Task] = None
        self._setup_ui()
        self._load_list("Stocks")

        # Refresh timer (every 10 seconds while visible)
        self._timer = QTimer(self)
        self._timer.setInterval(10_000)
        self._timer.timeout.connect(self._trigger_refresh)
        self._timer.start()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("panel_header")
        header.setStyleSheet("QWidget#panel_header { background:#161b22; border-bottom:1px solid #30363d; }")
        header.setFixedHeight(44)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 0, 10, 0)
        h_layout.setSpacing(6)

        title = QLabel("Watchlist")
        title.setObjectName("label_section")
        h_layout.addWidget(title)
        h_layout.addStretch()

        # Refresh button
        self._btn_refresh = QPushButton("↻")
        self._btn_refresh.setFixedSize(28, 28)
        self._btn_refresh.setToolTip("Refresh quotes")
        self._btn_refresh.clicked.connect(self._trigger_refresh)
        h_layout.addWidget(self._btn_refresh)

        layout.addWidget(header)

        # ── List selector tabs ─────────────────────────────────────────
        tabs = QWidget()
        tabs.setStyleSheet("background:#0d1117; border-bottom:1px solid #21262d;")
        t_layout = QHBoxLayout(tabs)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(4)

        self._tab_buttons: Dict[str, QPushButton] = {}
        for name in DEFAULT_WATCHLISTS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setStyleSheet("""
                QPushButton { background:transparent; border:1px solid transparent;
                              border-radius:4px; padding:0 10px; color:#8b949e; font-size:12px; }
                QPushButton:checked { background:#1f6feb22; border-color:#1f6feb; color:#58a6ff; }
                QPushButton:hover { background:#21262d; color:#e6edf3; }
            """)
            btn.clicked.connect(lambda checked, n=name: self._load_list(n))
            t_layout.addWidget(btn)
            self._tab_buttons[name] = btn
        t_layout.addStretch()
        layout.addWidget(tabs)

        # ── Search bar ────────────────────────────────────────────────
        search_bar = QWidget()
        search_bar.setStyleSheet("background:#0d1117; padding:0;")
        s_layout = QHBoxLayout(search_bar)
        s_layout.setContentsMargins(8, 6, 8, 6)
        s_layout.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Add symbol (e.g. AAPL, BTC-USD)...")
        self._search.setFixedHeight(30)
        self._search.returnPressed.connect(self._add_symbol)
        s_layout.addWidget(self._search)

        btn_add = QPushButton("+")
        btn_add.setFixedSize(30, 30)
        btn_add.setObjectName("btn_primary")
        btn_add.setToolTip("Add symbol to watchlist")
        btn_add.clicked.connect(self._add_symbol)
        s_layout.addWidget(btn_add)

        layout.addWidget(search_bar)

        # ── Table ──────────────────────────────────────────────────────
        self._table = QTableWidget(0, len(COLS))
        self._table.setHorizontalHeaderLabels(COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(COL_SYMBOL, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(COL_SYMBOL, 80)
        self._table.setColumnWidth(COL_PRICE, 80)
        self._table.setColumnWidth(COL_CHANGE, 70)
        self._table.setColumnWidth(COL_CHANGEP, 60)
        self._table.setRowHeight(0, 32)
        self._table.cellClicked.connect(self._on_row_clicked)
        layout.addWidget(self._table)

        # ── Status line ────────────────────────────────────────────────
        self._status_label = QLabel("Loading…")
        self._status_label.setObjectName("label_muted")
        self._status_label.setContentsMargins(10, 4, 0, 4)
        self._status_label.setFixedHeight(24)
        self._status_label.setStyleSheet("font-size:11px; color:#484f58;")
        layout.addWidget(self._status_label)

    # ── List Management ────────────────────────────────────────────────────

    def _load_list(self, name: str):
        self._active_list = name
        for n, btn in self._tab_buttons.items():
            btn.setChecked(n == name)
        self._symbols = list(DEFAULT_WATCHLISTS[name])
        self._rebuild_table()
        self._trigger_refresh()

    def _add_symbol(self):
        text = self._search.text().strip().upper()
        if not text:
            return
        if text not in self._symbols:
            self._symbols.append(text)
            self._rebuild_table()
            self._trigger_refresh()
        self._search.clear()

    def _rebuild_table(self):
        self._table.setRowCount(0)
        for symbol in self._symbols:
            self._insert_row(symbol)
        self._update_from_cache()

    def _insert_row(self, symbol: str):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setRowHeight(row, 32)

        sym_item = _item(symbol, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        sym_item.setData(Qt.ItemDataRole.UserRole, symbol)
        f = sym_item.font()
        f.setWeight(QFont.Weight.Medium)
        sym_item.setFont(f)
        sym_item.setForeground(QBrush(QColor("#e6edf3")))
        self._table.setItem(row, COL_SYMBOL, sym_item)

        for col in [COL_PRICE, COL_CHANGE, COL_CHANGEP, COL_VOLUME]:
            self._table.setItem(row, col, _item("--"))

    def _on_row_clicked(self, row: int, _col: int):
        item = self._table.item(row, COL_SYMBOL)
        if item:
            self.symbol_selected.emit(item.data(Qt.ItemDataRole.UserRole))

    # ── Quote Updates ──────────────────────────────────────────────────────

    def _trigger_refresh(self):
        """Schedule async quote fetch via the running event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._fetch_quotes())
        except RuntimeError:
            pass

    async def _fetch_quotes(self):
        self._status_label.setText("Updating…")
        try:
            # Import here to avoid circular at module load
            from data.feed import data_feed
            quotes = await data_feed.get_multiple_quotes(self._symbols)
            self._quotes.update(quotes)
            self._update_from_cache()
            self._status_label.setText(f"Updated — {len(quotes)} symbols")
        except Exception as e:
            self._status_label.setText(f"Error: {e}")

    def _update_from_cache(self):
        for row in range(self._table.rowCount()):
            sym_item = self._table.item(row, COL_SYMBOL)
            if not sym_item:
                continue
            symbol = sym_item.data(Qt.ItemDataRole.UserRole)
            q = self._quotes.get(symbol)
            if not q:
                continue
            self._update_row(row, q)

    def _update_row(self, row: int, q: Dict):
        price = q.get("price")
        open_ = q.get("open")

        price_str = f"{price:.4f}" if price else "--"
        price_item = _item(price_str)
        price_item.setForeground(QBrush(QColor("#e6edf3")))
        self._table.setItem(row, COL_PRICE, price_item)

        if price and open_:
            change = price - open_
            change_pct = (change / open_) * 100
            is_up = change >= 0
            color = C_GREEN if is_up else C_RED
            sign = "+" if is_up else ""

            ch_item = _item(f"{sign}{change:.2f}")
            ch_item.setForeground(QBrush(color))
            self._table.setItem(row, COL_CHANGE, ch_item)

            chp_item = _item(f"{sign}{change_pct:.2f}%")
            chp_item.setForeground(QBrush(color))
            self._table.setItem(row, COL_CHANGEP, chp_item)
        else:
            for col in [COL_CHANGE, COL_CHANGEP]:
                self._table.setItem(row, col, _item("--"))

        vol = q.get("volume")
        vol_item = _item(_fmt_volume(vol))
        vol_item.setForeground(QBrush(C_MUTED))
        self._table.setItem(row, COL_VOLUME, vol_item)
