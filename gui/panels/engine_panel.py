"""
[Paky] Engine Panel — Stato del motore automatico + controlli

Mostra in tempo reale:
  - Stato motore (Running / Stopped)
  - Equity corrente, P&L giornaliero, drawdown
  - Ultimo scan per strumento
  - Alert di trend change
  - Bottone Start/Stop

Fase 5.2: 4 StatusDot per loop async + listener loop_heartbeat + timeout idle 60s.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QVBoxLayout, QHBoxLayout,
)

from core.signal_bus import (
    get_bus, EngineStatusEvent, TrendAlertEvent, ScanResultEvent,
    TradeOpenedEvent, TradeClosedEvent,
)
from gui.widgets.info import StatusDot, HelpIcon

_UI = Path(__file__).parent.parent / "ui" / "engine_panel.ui"

# ─── Stili ───────────────────────────────────────────────────────────────────

_STYLE_GREEN  = "color: #3fb950; font-weight: bold;"
_STYLE_RED    = "color: #f85149; font-weight: bold;"
_STYLE_YELLOW = "color: #e3b341; font-weight: bold;"
_STYLE_GRAY   = "color: #a8b1bb;"
_STYLE_WHITE  = "color: #e6edf3;"


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border: 1px solid #21262d;")
    return f


# ─────────────────────────────────────────────────────────────────────────────
_LOOP_NAMES = ["4h_scan", "1h_scan", "trend_detect", "position_check"]
_IDLE_TIMEOUT_MS = 60_000  # 60 secondi senza heartbeat → idle


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
        self._build_loop_dots()
        self._add_help_icon()
        self._setup_connections()
        self._connect_bus()
        self._connect_language_bus()

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
            QGroupBox { color:#a8b1bb; font-size:11px; border:1px solid #30363d;
                        border-radius:4px; margin-top:6px; padding-top:4px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; }
        """)
        self.alertGroup.setStyleSheet("""
            QGroupBox { color:#e3b341; font-size:11px; border:1px solid #30363d;
                        border-radius:4px; margin-top:6px; padding-top:4px; }
            QGroupBox::title { subcontrol-origin:margin; left:8px; }
        """)

    def _build_loop_dots(self):
        """Fase 5.2 — Crea 4 StatusDot per i loop async e li inserisce dopo metricsFrame."""
        from gui.i18n import tr

        dots_frame = QFrame()
        dots_frame.setStyleSheet(
            "QFrame { background:#161b22; border:1px solid #30363d; border-radius:6px; }"
        )
        dots_layout = QVBoxLayout(dots_frame)
        dots_layout.setContentsMargins(10, 8, 10, 8)
        dots_layout.setSpacing(6)

        title_lbl = QLabel("Loop Status")
        title_lbl.setStyleSheet("color:#a8b1bb; font-size:10px; font-weight:bold;")
        dots_layout.addWidget(title_lbl)

        self._loop_dots: Dict[str, StatusDot] = {}
        self._loop_timers: Dict[str, QTimer] = {}

        for loop_name in _LOOP_NAMES:
            label_text = tr(f"engine.loop.{loop_name}")
            row_w = QWidget()
            row_hl = QHBoxLayout(row_w)
            row_hl.setContentsMargins(0, 0, 0, 0)
            row_hl.setSpacing(6)

            dot = StatusDot()
            dot.set_state("idle")
            dot.set_label(label_text)
            self._loop_dots[loop_name] = dot
            row_hl.addWidget(dot)
            row_hl.addStretch()
            dots_layout.addWidget(row_w)

            # Timer timeout idle: se non riceviamo heartbeat per 60s → idle
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(_IDLE_TIMEOUT_MS)
            # Closure per catturare loop_name correttamente
            t.timeout.connect(
                (lambda lname: lambda: self._loop_dots[lname].set_state("idle"))(loop_name)
            )
            self._loop_timers[loop_name] = t

        # Inserisco il frame dei dots subito dopo metricsFrame nel rootLayout
        try:
            idx = self.rootLayout.indexOf(self.metricsFrame)
            self.rootLayout.insertWidget(idx + 1, dots_frame)
        except Exception:
            self.rootLayout.addWidget(dots_frame)

    def _add_help_icon(self):
        """Inserisce HelpIcon accanto al titolo nel headerLayout."""
        from gui.i18n import tr
        self._help_icon = HelpIcon(tr("help.engine.title"), tr("help.engine.body"))
        # headerLayout è un QHBoxLayout diretto nel rootLayout — titolo all'index 0
        header_layout = self.rootLayout.itemAt(0).layout()
        if header_layout is not None:
            header_layout.insertWidget(1, self._help_icon)

    def _connect_language_bus(self):
        """Aggiorna HelpIcon al cambio lingua runtime."""
        from gui.i18n import tr
        try:
            get_bus().qt.language_changed.connect(lambda _: self._help_icon.update_texts(
                tr("help.engine.title"), tr("help.engine.body")
            ))
        except Exception:
            pass

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
        # Fase 5.2 — heartbeat loop async
        bus.qt.loop_heartbeat.connect(self._on_loop_heartbeat)

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
            color = "#a8b1bb"; icon = "—"

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
        meta.setStyleSheet("color:#a8b1bb; font-size:10px;")
        cl.addWidget(meta)

        sigs = QLabel(f"{len(ev.signals)} segnali: " + " · ".join(
            s.split("(")[0].strip() for s in ev.signals[:3]
        ))
        sigs.setStyleSheet("color:#a8b1bb; font-size:10px;")
        sigs.setWordWrap(True)
        cl.addWidget(sigs)

        count = self._alert_layout.count()
        self._alert_layout.insertWidget(count - 1, card)

        # Max 10 alerts
        while self._alert_layout.count() > 11:
            item = self._alert_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    @pyqtSlot(str)
    def _on_loop_heartbeat(self, loop_name: str):
        """Fase 5.2 — heartbeat: flash dot active + reset timer idle 60s."""
        dot = self._loop_dots.get(loop_name)
        if dot is None:
            return
        dot.set_state("active")
        dot.pulse()
        # Reset timer idle: se arriva un altro heartbeat entro 60s, il reset continua
        timer = self._loop_timers.get(loop_name)
        if timer:
            timer.start()

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
