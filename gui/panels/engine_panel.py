"""
[Paky] Engine Panel — Stato del motore automatico + controlli

Mostra in tempo reale:
  - Stato motore (Running / Stopped)
  - Equity corrente, P&L giornaliero, drawdown
  - Ultimo scan per strumento
  - Alert di trend change
  - Bottone Start/Stop
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout,
)

from core.signal_bus import (
    get_bus, EngineStatusEvent, TrendAlertEvent, ScanResultEvent,
    TradeOpenedEvent, TradeClosedEvent,
)

_UI = Path(__file__).parent.parent / "ui" / "engine_panel.ui"

# ─── Stili ───────────────────────────────────────────────────────────────────

_STYLE_GREEN  = "color: #3fb950; font-weight: bold;"
_STYLE_RED    = "color: #f85149; font-weight: bold;"
_STYLE_YELLOW = "color: #e3b341; font-weight: bold;"
_STYLE_GRAY   = "color: #8b949e;"
_STYLE_WHITE  = "color: #e6edf3;"


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border: 1px solid #21262d;")
    return f


# ─────────────────────────────────────────────────────────────────────────────
class EnginePanel(QWidget):
    """Pannello di controllo e monitoraggio del motore automatico."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._engine  = None    # reference al TradingEngine (impostato da app.py)

        uic.loadUi(str(_UI), self)

        # Ripristina i margini rimossi dal .ui per compatibilità PyQt6 uic
        self.rootLayout.setContentsMargins(8, 8, 8, 8)
        self.metricsLayout.setContentsMargins(10, 8, 10, 8)
        self.scanGroupLayout.setContentsMargins(6, 6, 6, 6)
        self.alertGroupLayout.setContentsMargins(6, 6, 6, 6)

        # Get layout references from named container widgets
        self._scan_layout   = self._scan_container.layout()
        self._alert_layout  = self._alert_container.layout()

        # Add stretch at end of each scroll container
        self._scan_layout.addStretch()
        self._alert_layout.addStretch()

        self._setup_styles()
        self._setup_connections()
        self._connect_bus()

    # ─────────────────────────────────────────────────────────────────────
    # Setup
    # ─────────────────────────────────────────────────────────────────────

    def _setup_styles(self):
        self._lbl_title.setStyleSheet(
            "color:#e6edf3; font-size:13px; font-weight:bold;")
        self._lbl_state.setStyleSheet(_STYLE_GRAY)
        self._lbl_equity.setStyleSheet(_STYLE_WHITE)
        self._lbl_pnl.setStyleSheet(_STYLE_GRAY)
        self._lbl_return.setStyleSheet(_STYLE_GRAY)
        self._lbl_dd.setStyleSheet(_STYLE_GRAY)
        self._lbl_positions.setStyleSheet(_STYLE_GRAY)

        # Caption labels
        for name in ("lblEquityCaption", "lblPnlCaption", "lblReturnCaption",
                     "lblDdCaption", "lblPosCaption"):
            lbl = self.findChild(QLabel, name)
            if lbl:
                lbl.setStyleSheet(_STYLE_GRAY)

        self._btn_start.setStyleSheet("""
            QPushButton {
                background: #238636; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #2ea043; }
            QPushButton:pressed { background: #1a7f37; }
        """)
        self.metricsFrame.setStyleSheet("""
            QFrame {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
        """)
        self.scanGroup.setStyleSheet("""
            QGroupBox { color:#8b949e; font-size:11px; border:1px solid #30363d;
                        border-radius:4px; margin-top:6px; padding-top:4px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; }
        """)
        self.alertGroup.setStyleSheet("""
            QGroupBox { color:#e3b341; font-size:11px; border:1px solid #30363d;
                        border-radius:4px; margin-top:6px; padding-top:4px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; }
        """)

    def _setup_connections(self):
        self._btn_start.clicked.connect(self._on_start_stop)

    # ─────────────────────────────────────────────────────────────────────
    # Bus connections
    # ─────────────────────────────────────────────────────────────────────

    def _connect_bus(self):
        bus = get_bus()
        bus.qt.engine_status.connect(self._on_status)
        bus.qt.engine_started.connect(self._on_engine_started)
        bus.qt.engine_stopped.connect(self._on_engine_stopped)
        bus.qt.scan_result.connect(self._on_scan_result)
        bus.qt.trend_alert.connect(self._on_trend_alert)

    # ─────────────────────────────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_status(self, ev: EngineStatusEvent):
        self._lbl_equity.setText(f"€ {ev.equity:,.2f}")

        pnl_style = _STYLE_GREEN if ev.daily_pnl >= 0 else _STYLE_RED
        self._lbl_pnl.setText(f"€ {ev.daily_pnl:+.2f}")
        self._lbl_pnl.setStyleSheet(pnl_style)

        ret_style = _STYLE_GREEN if ev.total_return_pct >= 0 else _STYLE_RED
        self._lbl_return.setText(f"{ev.total_return_pct:+.2f}%")
        self._lbl_return.setStyleSheet(ret_style)

        dd_style = _STYLE_GREEN if ev.drawdown_pct < 3 else (
            _STYLE_YELLOW if ev.drawdown_pct < 7 else _STYLE_RED
        )
        self._lbl_dd.setText(f"{ev.drawdown_pct:.1f}%")
        self._lbl_dd.setStyleSheet(dd_style)

        self._lbl_positions.setText(str(ev.open_positions))

    @pyqtSlot()
    def _on_engine_started(self):
        self._running = True
        self._lbl_state.setText("● ATTIVO")
        self._lbl_state.setStyleSheet(_STYLE_GREEN)
        self._btn_start.setText("■  Ferma Engine")
        self._btn_start.setStyleSheet("""
            QPushButton {
                background: #6e271e; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #f85149; }
        """)

    @pyqtSlot()
    def _on_engine_stopped(self):
        self._running = False
        self._lbl_state.setText("⏸ FERMO")
        self._lbl_state.setStyleSheet(_STYLE_GRAY)
        self._btn_start.setText("▶  Avvia Engine")
        self._btn_start.setStyleSheet("""
            QPushButton {
                background: #238636; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover { background: #2ea043; }
        """)

    @pyqtSlot(object)
    def _on_scan_result(self, ev: ScanResultEvent):
        """Aggiunge riga agli ultimi segnali."""
        ts = ev.timestamp.strftime("%H:%M")

        if ev.direction == "buy":
            color = "#3fb950"; icon = "▲"
        elif ev.direction == "sell":
            color = "#f85149"; icon = "▼"
        else:
            color = "#8b949e"; icon = "—"

        text = f"{ts}  {icon} {ev.display:8s}  conf={ev.confidence:.2f}  [{ev.strategy}]"
        row = QLabel(text)
        row.setStyleSheet(f"color:{color}; font-size:11px; font-family:monospace;")
        row.setWordWrap(False)

        # Inserisci prima dello stretch
        count = self._scan_layout.count()
        self._scan_layout.insertWidget(count - 1, row)

        # Max 20 righe
        while self._scan_layout.count() > 21:
            item = self._scan_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    @pyqtSlot(object)
    def _on_trend_alert(self, ev: TrendAlertEvent):
        """Aggiunge un alert di trend change."""
        ts = ev.timestamp.strftime("%H:%M")

        if "bull" in ev.alert_type:
            color = "#3fb950"; emoji = "🔼"
        else:
            color = "#f85149"; emoji = "🔽"

        # Card alert
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #161b22;
                border-left: 3px solid {color};
                border-radius: 3px;
                padding: 2px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(6, 4, 6, 4)
        cl.setSpacing(2)

        conf_text = f"{emoji} {ev.display} — {ev.alert_type.upper().replace('_', ' ')}"
        title = QLabel(conf_text)
        title.setStyleSheet(f"color:{color}; font-size:11px; font-weight:bold;")
        cl.addWidget(title)

        meta = QLabel(f"Conf: {ev.confidence:.0f}%  |  {ts}  |  {ev.timeframe}")
        meta.setStyleSheet("color:#8b949e; font-size:10px;")
        cl.addWidget(meta)

        sigs = QLabel(f"{len(ev.signals)} segnali: " + " · ".join(
            s.split("(")[0].strip() for s in ev.signals[:3]
        ))
        sigs.setStyleSheet("color:#8b949e; font-size:10px;")
        sigs.setWordWrap(True)
        cl.addWidget(sigs)

        count = self._alert_layout.count()
        self._alert_layout.insertWidget(count - 1, card)

        # Max 10 alerts
        while self._alert_layout.count() > 11:
            item = self._alert_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ─────────────────────────────────────────────────────────────────────
    # Start/Stop
    # ─────────────────────────────────────────────────────────────────────

    def _on_start_stop(self):
        import asyncio
        if self._running:
            if self._engine:
                asyncio.ensure_future(self._engine.stop())
        else:
            if self._engine is None:
                from core.engine import TradingEngine
                self._engine = TradingEngine(capital=1000.0, mode="paper")
            asyncio.ensure_future(self._engine.run())

    def set_engine(self, engine):
        """Chiamato da app.py per collegare l'engine al pannello."""
        self._engine = engine
