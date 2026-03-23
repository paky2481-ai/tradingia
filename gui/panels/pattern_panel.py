"""
Pattern Panel — Mostra la coda di osservazione pattern in tempo reale.

Colonne: Symbol | Pattern | Direzione | Status | Conf% | TF | Da | Target
Colori  : forming=arancio, confirmed=verde, failed=rosso, expired=grigio

Aggiornamento:
  - Real-time: slot connesso a signal_bus.pattern_alert (emit da orchestrator)
  - Polling fallback: QTimer ogni 5s (interroga l'observer direttamente)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QHeaderView, QAbstractItemView, QComboBox,
)

from core.signal_bus import get_bus, PatternAlertEvent
from core.pattern_observer import get_pattern_observer
from utils.logger import get_logger

logger = get_logger.bind(name="gui.pattern_panel")

# Colori per stato
_COLORS = {
    "forming":   "#d29922",   # giallo-arancio
    "confirmed": "#3fb950",   # verde
    "failed":    "#f85149",   # rosso
    "expired":   "#484f58",   # grigio scuro
    "bullish":   "#3fb950",
    "bearish":   "#f85149",
    "neutral":   "#8b949e",
}

_COLUMNS = ["Symbol", "Pattern", "Direzione", "Status", "Conf%", "TF", "Da (min)", "Target"]


class PatternPanel(QWidget):
    """Pannello di monitoraggio pattern in tempo reale."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._rows: dict[str, int] = {}   # observation_id → row index
        self._setup_ui()
        self._connect_bus()
        self._start_polling()

    # ── UI setup ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Header ────────────────────────────────────────────────────────
        header = QHBoxLayout()

        title = QLabel("Pattern in Osservazione")
        title.setStyleSheet("color:#e6edf3; font-weight:bold; font-size:13px;")
        header.addWidget(title)

        header.addStretch()

        self._lbl_count = QLabel("0 pattern")
        self._lbl_count.setStyleSheet("color:#8b949e; font-size:11px;")
        header.addWidget(self._lbl_count)

        # Filtro per status
        self._status_filter = QComboBox()
        self._status_filter.addItems(["Tutti", "forming", "confirmed", "failed", "expired"])
        self._status_filter.setFixedWidth(100)
        self._status_filter.setStyleSheet(
            "background:#21262d; color:#e6edf3; border:1px solid #30363d; "
            "border-radius:4px; padding:2px 6px; font-size:11px;"
        )
        self._status_filter.currentTextChanged.connect(self._refresh_table)
        header.addWidget(self._status_filter)

        btn_clear = QPushButton("Pulisci terminati")
        btn_clear.setFixedHeight(26)
        btn_clear.setStyleSheet(
            "background:#21262d; color:#8b949e; border:1px solid #30363d; "
            "border-radius:4px; padding:2px 8px; font-size:11px;"
        )
        btn_clear.clicked.connect(self._clear_terminal)
        header.addWidget(btn_clear)

        root.addLayout(header)

        # ── Tabella ────────────────────────────────────────────────────────
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        # Larghezze colonne
        widths = [70, 170, 80, 80, 55, 50, 70, 90]
        for i, w in enumerate(widths):
            self._table.setColumnWidth(i, w)

        self._table.setStyleSheet("""
            QTableWidget {
                background:#0d1117; color:#e6edf3;
                border:none; gridline-color:#21262d;
                font-size:11px;
            }
            QTableWidget::item:selected {
                background:#1c2128; color:#e6edf3;
            }
            QHeaderView::section {
                background:#161b22; color:#8b949e;
                border:none; border-bottom:1px solid #30363d;
                padding:4px 6px; font-size:11px;
            }
        """)
        self._table.setRowHeight(0, 26)
        root.addWidget(self._table)

    # ── Bus connection ─────────────────────────────────────────────────────

    def _connect_bus(self):
        bus = get_bus()
        bus.qt.pattern_alert.connect(self._on_pattern_alert)

    @pyqtSlot(object)
    def _on_pattern_alert(self, event: PatternAlertEvent):
        """Riceve eventi real-time dall'orchestrator e aggiorna la tabella."""
        self._upsert_row(
            obs_id=event.observation_id or f"{event.symbol}_{event.pattern_name}",
            symbol=event.symbol,
            pattern=event.pattern_name,
            direction=event.direction,
            status=event.status,
            confidence=event.confidence,
            timeframe=event.timeframe,
            forming_since=event.timestamp,
            target=event.target_price,
        )

    # ── Polling (fallback + aggiornamento Da) ─────────────────────────────

    def _start_polling(self):
        self._timer = QTimer(self)
        self._timer.setInterval(5000)   # ogni 5s
        self._timer.timeout.connect(self._poll_observer)
        self._timer.start()

    def _poll_observer(self):
        """Interroga l'observer per aggiornare la colonna 'Da (min)'."""
        observer = get_pattern_observer()
        for symbol, obs_list in observer._obs.items():
            for obs in obs_list:
                key = obs.id or f"{symbol}_{obs.raw.name}"
                row = self._rows.get(key)
                if row is None:
                    # Pattern non ancora in tabella (es. da sessione precedente)
                    self._upsert_row(
                        obs_id=obs.id,
                        symbol=symbol,
                        pattern=obs.raw.name,
                        direction=obs.raw.direction,
                        status=obs.status,
                        confidence=obs.raw.confidence,
                        timeframe=obs.raw.timeframe,
                        forming_since=obs.forming_since,
                        target=obs.raw.target_price,
                    )
                else:
                    # Aggiorna solo la colonna "Da (min)"
                    age_min = int(obs.age_seconds / 60)
                    item = self._table.item(row, 6)
                    if item:
                        item.setText(str(age_min))

        self._update_count()

    # ── Table management ───────────────────────────────────────────────────

    def _upsert_row(
        self,
        obs_id: str,
        symbol: str,
        pattern: str,
        direction: str,
        status: str,
        confidence: float,
        timeframe: str,
        forming_since: datetime,
        target: Optional[float],
    ):
        """Inserisce o aggiorna una riga per questo pattern."""
        # Controlla se la riga è già presente
        row = self._rows.get(obs_id)
        if row is None:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._rows[obs_id] = row

        age_min = max(0, int((datetime.utcnow() - forming_since).total_seconds() / 60))
        target_str = f"{target:.5g}" if target is not None else "—"
        status_col = _COLORS.get(status, "#8b949e")
        dir_col    = _COLORS.get(direction, "#8b949e")

        cells = [
            (symbol,                   "#c9d1d9"),
            (pattern,                  "#e6edf3"),
            (direction.capitalize(),   dir_col),
            (status.upper(),           status_col),
            (f"{confidence * 100:.0f}%", "#8b949e"),
            (timeframe,                "#8b949e"),
            (str(age_min),             "#8b949e"),
            (target_str,               "#8b949e"),
        ]

        for col, (text, color) in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setForeground(QColor(color))
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._table.setItem(row, col, item)

        self._table.setRowHeight(row, 24)

        # Evidenzia la riga intera per lo stato
        if status == "confirmed":
            for col in range(len(_COLUMNS)):
                it = self._table.item(row, col)
                if it:
                    it.setBackground(QColor("#0d2a14"))
        elif status == "failed":
            for col in range(len(_COLUMNS)):
                it = self._table.item(row, col)
                if it:
                    it.setBackground(QColor("#2d0f0f"))

        self._update_count()

        # Applica filtro corrente
        filter_status = self._status_filter.currentText()
        self._table.setRowHidden(
            row,
            filter_status not in ("Tutti", status),
        )

    def _update_count(self):
        total = self._table.rowCount()
        forming = sum(
            1 for r in range(total)
            if (self._table.item(r, 3) or QTableWidgetItem("")).text() == "FORMING"
        )
        self._lbl_count.setText(f"{total} pattern ({forming} forming)")

    def _refresh_table(self):
        """Riapplica il filtro status a tutte le righe."""
        filter_status = self._status_filter.currentText()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 3)
            status = (item.text() if item else "").lower()
            self._table.setRowHidden(
                row,
                filter_status not in ("Tutti", status),
            )

    def _clear_terminal(self):
        """Rimuove le righe con status FAILED o EXPIRED dalla tabella."""
        rows_to_remove = []
        for row in range(self._table.rowCount() - 1, -1, -1):
            item = self._table.item(row, 3)
            if item and item.text() in ("FAILED", "EXPIRED"):
                rows_to_remove.append(row)

        for row in rows_to_remove:
            self._table.removeRow(row)

        # Ricostruisce il mapping id→row
        self._rows = {}
        self._update_count()
