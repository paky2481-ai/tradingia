"""
[Marco] Portfolio Panel — Fase 5.2

Mostra in tempo reale:
  - Heatmap correlazioni tra posizioni aperte (bus.qt.correlation_update)
  - Pie chart asset class (placeholder — fuori scope)
  - Gauge drawdown corrente (bus.qt.position_update)

Layout: QVBoxLayout con 3 sezioni (Heatmap, Asset Class, Drawdown).
"""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy,
)

from core.signal_bus import get_bus, PositionUpdateEvent, CorrelationUpdateEvent
from gui.i18n import tr
from gui.widgets.info import Heatmap, Gauge, HelpIcon


# ── Helper ────────────────────────────────────────────────────────────────────

def _section_header(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setStyleSheet(
        "color:#58a6ff; font-size:10px; font-weight:bold; "
        "border-bottom:1px solid #21262d; padding-bottom:2px; padding-top:4px;"
    )
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border:none; border-top:1px solid #21262d;")
    f.setFixedHeight(1)
    return f


# ── Panel ─────────────────────────────────────────────────────────────────────

class PortfolioPanel(QWidget):
    """
    Pannello portfolio con heatmap correlazioni + gauge drawdown.

    Fase 5.2 — listener:
        bus.qt.correlation_update  → aggiorna Heatmap
        bus.qt.position_update     → ricalcola drawdown corrente

    Uso:
        panel = PortfolioPanel()
        # integrazione in workspace a cura di Paky (task successivo)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        # Storico PnL non realizzato per ogni simbolo (symbol → pnl)
        self._position_pnl: Dict[str, float] = {}

        self._setup_ui()
        self._connect_bus()

    # ─────────────────────────────────────────────────────────────────────
    # Setup UI
    # ─────────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet("background:#0d1117; color:#e6edf3;")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── Titolo + HelpIcon ─────────────────────────────────────────────
        title_row = QWidget()
        title_hl = QHBoxLayout(title_row)
        title_hl.setContentsMargins(0, 0, 0, 0)
        title_hl.setSpacing(6)
        title = QLabel(tr("portfolio.title"))
        title.setStyleSheet(
            "color:#e6edf3; font-size:13px; font-weight:bold;"
        )
        title_hl.addWidget(title)
        self._help_icon = HelpIcon(tr("help.portfolio.title"), tr("help.portfolio.body"))
        title_hl.addWidget(self._help_icon)
        title_hl.addStretch()
        root.addWidget(title_row)
        root.addWidget(_sep())

        # ── Sezione Heatmap correlazioni ──────────────────────────────────
        root.addWidget(_section_header(tr("portfolio.correlations")))

        self._heatmap = Heatmap()
        self._heatmap.setMinimumHeight(160)
        self._heatmap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Placeholder dati demo (3×3 identità) finché non arriva correlation_update
        _demo = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        self._heatmap.set_matrix(_demo, ["—", "—", "—"])
        root.addWidget(self._heatmap, stretch=3)

        root.addWidget(_sep())

        # ── Sezione Asset Class (placeholder) ────────────────────────────
        root.addWidget(_section_header(tr("portfolio.asset_class")))

        placeholder = QLabel("Asset Class Distribution")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "color:#6e7681; font-size:11px; background:#161b22; "
            "border:1px dashed #30363d; border-radius:4px; padding:16px;"
        )
        placeholder.setFixedHeight(60)
        root.addWidget(placeholder)

        root.addWidget(_sep())

        # ── Sezione Drawdown gauge ────────────────────────────────────────
        root.addWidget(_section_header(tr("portfolio.drawdown")))

        dd_row = QWidget()
        dd_hl = QHBoxLayout(dd_row)
        dd_hl.setContentsMargins(0, 4, 0, 0)
        dd_hl.setSpacing(8)

        # Gauge drawdown: 0=no drawdown (verde), 0.5=attenzione (giallo), 1=max (rosso)
        # Zone invertite rispetto Hurst: verde basso, rosso alto
        self._gauge_drawdown = Gauge(
            label=tr("portfolio.drawdown"),
            width=200,
            height=28,
            zones=[
                (0.0, 0.05, "#3fb950"),   # < 5% — OK
                (0.05, 0.15, "#d29922"),  # 5-15% — warning
                (0.15, 1.0, "#f85149"),   # > 15% — danger
            ],
        )
        dd_hl.addWidget(self._gauge_drawdown)

        self._lbl_dd_value = QLabel("0.0%")
        self._lbl_dd_value.setStyleSheet(
            "color:#3fb950; font-size:12px; font-weight:bold; font-family:monospace;"
        )
        dd_hl.addWidget(self._lbl_dd_value)
        dd_hl.addStretch()

        root.addWidget(dd_row)

        root.addStretch(1)

    # ─────────────────────────────────────────────────────────────────────
    # Bus connections
    # ─────────────────────────────────────────────────────────────────────

    def _connect_bus(self) -> None:
        try:
            bus = get_bus()
            bus.qt.correlation_update.connect(self._on_correlation_update)
            bus.qt.position_update.connect(self._on_position_update)
            bus.qt.language_changed.connect(lambda _: self._help_icon.update_texts(
                tr("help.portfolio.title"), tr("help.portfolio.body")
            ))
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_correlation_update(self, event: CorrelationUpdateEvent) -> None:
        """Aggiorna heatmap con la nuova matrice correlazioni."""
        try:
            matrix = event.matrix
            symbols = event.symbols
            if hasattr(matrix, "tolist"):
                # np.ndarray → list
                matrix = matrix.tolist()
            self._heatmap.set_matrix(matrix, symbols)
        except Exception:
            pass

    @pyqtSlot(object)
    def _on_position_update(self, event: PositionUpdateEvent) -> None:
        """
        Ricalcola drawdown corrente dalle posizioni aperte.
        Drawdown = (peak_equity - current_equity) / peak_equity, clamped [0, 1].
        """
        try:
            # Aggiorna PnL per questo simbolo
            self._position_pnl[event.symbol] = event.unrealized_pnl

            # Equity corrente = sum pnl (semplificato: senza equity base)
            # In prod verrà da EngineStatusEvent. Qui usiamo la variazione PnL.
            total_pnl = sum(self._position_pnl.values())

            # Peak tracking
            if total_pnl > self._peak_equity:
                self._peak_equity = total_pnl

            if self._peak_equity > 0:
                dd = (self._peak_equity - total_pnl) / self._peak_equity
            else:
                dd = 0.0

            dd = max(0.0, min(1.0, dd))

            self._gauge_drawdown.set_value(dd)

            dd_pct = dd * 100
            if dd < 0.05:
                color = "#3fb950"
            elif dd < 0.15:
                color = "#d29922"
            else:
                color = "#f85149"

            self._lbl_dd_value.setText(f"{dd_pct:.1f}%")
            self._lbl_dd_value.setStyleSheet(
                f"color:{color}; font-size:12px; font-weight:bold; font-family:monospace;"
            )
        except Exception:
            pass
