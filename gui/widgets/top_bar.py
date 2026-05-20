"""
TopBar — barra superiore Bloomberg-style, altezza fissa 42px.

Contiene tutti i KPI globali del sistema, connessi ad AppState via segnali.
Layout orizzontale:
    [EngineBtn] | [EQUITY+sparkline] [P&L DAY] [POS] [WIN%] [RegimePill] |
    [Mode] [Broker] ---spacer--- [ClockUTC] [HelpIcon]

Connessioni live via AppState.instance():
    - engine_running_changed   → testo/colore bottone
    - equity_changed           → KPI EQUITY + sparkline sliding window
    - daily_pnl_changed        → KPI P&L DAY con flash 100ms
    - open_positions_changed   → KPI POS
    - win_rate_changed         → KPI WIN
    - current_regime_changed   → RegimePill
    - current_hurst_changed    → RegimePill
    - mode_changed             → Mode pill
    - broker_latency_changed   → Broker pill
"""
from __future__ import annotations

import random
from collections import deque
from datetime import datetime, timezone

from PyQt6.QtCore import QPropertyAnimation, QTimer, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState
from gui.widgets.info import HelpIcon, KPIBadge, RegimePill
from gui.widgets.info.status_dot import StatusDot


# ── Palette locale (coerente con dark.qss) ───────────────────────────────────
_BULL    = "#3fb950"
_BEAR    = "#f85149"
_WARN    = "#d29922"
_MUTED   = "#a8b1bb"
_TEXT    = "#e6edf3"
_BG_SURFACE = "#161b22"
_BORDER  = "#30363d"

# Finestra scorrevole equity per sparkline
_EQUITY_WINDOW = 50


def _make_separator() -> QFrame:
    """Linea verticale separatrice 1x26px con colore border dim."""
    sep = QFrame()
    sep.setObjectName("separator")
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFixedWidth(1)
    sep.setFixedHeight(26)
    sep.setStyleSheet("background:#30363d; border:none;")
    return sep


class _BrokerPill(QLabel):
    """
    Pallino colorato + latency ms.
    Esempio: "● 23ms" (verde) / "● ---" (rosso se non connesso).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connected = False
        self._latency = 0
        self._refresh()
        mono = '"Consolas", "Cascadia Code", monospace'
        self.setStyleSheet(
            f"font-family:{mono}; font-size:11px; background:transparent; border:none;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.setContentsMargins(0, 0, 0, 0)
        self.setToolTip(tr("tooltip.broker"))

    def update_state(self, connected: bool, latency_ms: int) -> None:
        self._connected = connected
        self._latency = latency_ms
        self._refresh()

    def _refresh(self) -> None:
        if self._connected:
            if self._latency < 50:
                color = _BULL
            elif self._latency < 200:
                color = _WARN
            else:
                color = _BEAR
            text = f"• {self._latency}ms"
        else:
            color = _BEAR
            text = "• ---"
        # vertical-align:middle allinea il bullet al centro della riga di testo
        self.setText(
            f'<span style="color:{color}; vertical-align:middle;">{text}</span>'
        )
        self.setTextFormat(Qt.TextFormat.RichText)


class _ModePill(QLabel):
    """
    PAPER (giallo) o LIVE (rosso) in base a AppState.mode.
    """

    _STYLES: dict[str, tuple[str, str]] = {
        "paper": (_WARN, "PAPER"),
        "live":  (_BEAR, "LIVE"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(18)
        self.setToolTip(tr("tooltip.mode"))
        self._apply("paper")

    def set_mode(self, mode: str) -> None:
        self._apply(mode.lower())

    def _apply(self, mode: str) -> None:
        color, label = self._STYLES.get(mode, (_MUTED, mode.upper()))
        self.setText(label)
        self.setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:700;"
            "  font-family:'Segoe UI','Inter',sans-serif;"
            f"  border:1px solid {color}; border-radius:4px;"
            "  padding:1px 6px; background:transparent;"
        )
        # Auto-width basato su testo
        self.adjustSize()


class _FlashLabel(QLabel):
    """
    QLabel con effetto flash di colore (100ms) su set_value_flash().
    Usato per P&L DAY live.
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._base_color = _TEXT
        self._anim: QPropertyAnimation | None = None

    def flash(self, color: str = _BULL) -> None:
        """Flash istantaneo: colore per 120ms poi torna al base."""
        self.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:700;"
            '  font-family:"Consolas","Cascadia Code",monospace;'
            "  background:transparent; border:none;"
        )
        QTimer.singleShot(
            120,
            lambda: self.setStyleSheet(
                f"color:{self._base_color}; font-size:13px; font-weight:700;"
                '  font-family:"Consolas","Cascadia Code",monospace;'
                "  background:transparent; border:none;"
            ),
        )


class _ScanChip(QWidget):
    """
    Fase B — indicatore "engine sta scansionando X".

    Layout: [StatusDot] [SCAN:] [EURUSD=X] [4h_scan]

    - Visibile SOLO quando engine running e un simbolo e' in scan.
    - StatusDot verde pulsante mentre in scan; idle quando fermo.
    - Si nasconde (hide) quando engine fermo o chip vuoto.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._dot = StatusDot(self)
        self._dot.set_state("idle")
        lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)

        lbl_prefix = QLabel(tr("topbar.scan_label"))
        lbl_prefix.setStyleSheet(
            f"color:{_MUTED}; font-size:10px; font-weight:600;"
            '  font-family:"Segoe UI","Inter",sans-serif;'
            "  background:transparent; border:none; letter-spacing:0.4px;"
        )
        lay.addWidget(lbl_prefix, 0, Qt.AlignmentFlag.AlignVCenter)

        self._symbol_lbl = QLabel("—")
        self._symbol_lbl.setStyleSheet(
            f"color:{_TEXT}; font-size:12px; font-weight:700;"
            '  font-family:"Consolas","Cascadia Code",monospace;'
            "  background:transparent; border:none;"
        )
        lay.addWidget(self._symbol_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self._loop_lbl = QLabel("")
        self._loop_lbl.setStyleSheet(
            f"color:{_MUTED}; font-size:9px; font-weight:500;"
            '  font-family:"Segoe UI","Inter",sans-serif;'
            "  background:transparent; border:none;"
        )
        lay.addWidget(self._loop_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setToolTip(tr("topbar.scan_tooltip"))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(20)

        # Timer idle — se non arriva un emit per 5s, torna a idle
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(5000)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

        # Nascosto di default (engine fermo)
        self.hide()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def update_scan(self, symbol: str, loop_name: str) -> None:
        """Aggiorna display e resetta timer idle. Se symbol vuoto: nasconde."""
        if not symbol:
            self._go_idle()
            return

        # Display human-readable
        try:
            from core.engine import INSTRUMENTS
            display = INSTRUMENTS.get(symbol, (symbol,))[0]
        except Exception:
            display = symbol

        self._symbol_lbl.setText(display)
        self._loop_lbl.setText(f"[{loop_name}]" if loop_name else "")
        self._dot.set_state("loading")
        self.show()

        # Riavvia il timer idle
        self._idle_timer.start()

    def engine_stopped(self) -> None:
        """Chiamato quando engine si ferma — nasconde subito."""
        self._idle_timer.stop()
        self._go_idle()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _go_idle(self) -> None:
        self._dot.set_state("idle")
        self._symbol_lbl.setText("—")
        self._loop_lbl.setText("")
        self.hide()

    def _on_idle_timeout(self) -> None:
        """5s senza emit: dot torna idle ma rimane visibile (engine running)."""
        self._dot.set_state("idle")


class TopBar(QFrame):
    """
    Barra superiore Bloomberg-style, 42px fissi.

    Connessa in sola lettura ad AppState.instance() — nessun dato viene
    mai scritto da qui (eccezione: toggle engine via bottone START/STOP
    che setta AppState.engine_running).

    Oggetto di test di render:
        bar = TopBar()
        bar.show()
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(42)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        # Sliding window equity per sparkline
        self._equity_history: deque[float] = deque(
            [10_000.0] * _EQUITY_WINDOW, maxlen=_EQUITY_WINDOW
        )
        self._last_pnl: float = 0.0
        self._last_hurst: float = 0.5

        self._build_ui()
        self._connect_state()

        # Timer clock UTC — tick ogni 1s
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    # ── Costruzione UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(10)

        # 1. Engine button ────────────────────────────────────────────────────
        self._engine_btn = QPushButton(tr("topbar.start"))
        self._engine_btn.setProperty("variant", "primary")
        self._engine_btn.setFixedSize(100, 28)
        self._engine_btn.setToolTip(tr("topbar.engine_start_tip"))
        self._engine_btn.clicked.connect(self._toggle_engine)
        lay.addWidget(self._engine_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(_make_separator())

        # 1b-engine. ScanChip (Fase B) — simbolo in scansione dal backend ────────
        self._scan_chip = _ScanChip()
        lay.addWidget(self._scan_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(_make_separator())

        # 1b. Symbol chip (Fase A.1) — simbolo correntemente selezionato ────────
        self._symbol_prefix = QLabel(tr("topbar.symbol_label"))
        self._symbol_prefix.setStyleSheet(
            f"color:{_MUTED}; font-size:10px; font-weight:600;"
            '  font-family:"Segoe UI","Inter",sans-serif;'
            "  background:transparent; border:none; letter-spacing:0.4px;"
        )
        lay.addWidget(self._symbol_prefix, 0, Qt.AlignmentFlag.AlignVCenter)

        self._symbol_chip = QLabel("—")
        self._symbol_chip.setStyleSheet(
            f"color:{_TEXT}; font-size:12px; font-weight:700;"
            '  font-family:"Consolas","Cascadia Code",monospace;'
            "  background:transparent; border:none;"
        )
        self._symbol_chip.setToolTip(tr("topbar.symbol_tooltip"))
        lay.addWidget(self._symbol_chip, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(_make_separator())

        # 2. EQUITY + sparkline ───────────────────────────────────────────────
        self._badge_equity = KPIBadge(
            tr("topbar.equity"),
            show_sparkline=True,
            sparkline_width=60,
            sparkline_height=20,
        )
        self._badge_equity.set_value("—")
        self._badge_equity.setToolTip(tr("tooltip.equity"))
        self._badge_equity.set_sparkline_values(list(self._equity_history))
        lay.addWidget(self._badge_equity, 0, Qt.AlignmentFlag.AlignVCenter)

        # 3. P&L DAY ──────────────────────────────────────────────────────────
        self._badge_pnl = KPIBadge(tr("topbar.pnl_day"))
        self._badge_pnl.set_value("—")
        self._badge_pnl.setToolTip(tr("tooltip.pnl_day"))
        lay.addWidget(self._badge_pnl, 0, Qt.AlignmentFlag.AlignVCenter)

        # 4. POS ──────────────────────────────────────────────────────────────
        self._badge_pos = KPIBadge(tr("topbar.positions"))
        self._badge_pos.set_value("0/5")
        self._badge_pos.setToolTip(tr("tooltip.positions"))
        lay.addWidget(self._badge_pos, 0, Qt.AlignmentFlag.AlignVCenter)

        # 5. WIN% ─────────────────────────────────────────────────────────────
        self._badge_win = KPIBadge(tr("topbar.win_rate"))
        self._badge_win.set_value("—")
        self._badge_win.setToolTip(tr("tooltip.win_rate"))
        lay.addWidget(self._badge_win, 0, Qt.AlignmentFlag.AlignVCenter)

        # 6. RegimePill ───────────────────────────────────────────────────────
        self._regime_pill = RegimePill()
        self._regime_pill.set_regime("unknown")
        lay.addWidget(self._regime_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(_make_separator())

        # 9. Spacer — spinge il blocco destra verso il margine destro ──────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(spacer)

        # 7. Mode pill ────────────────────────────────────────────────────────
        self._mode_pill = _ModePill()
        lay.addWidget(self._mode_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        # 8. Broker pill ──────────────────────────────────────────────────────
        self._broker_pill = _BrokerPill()
        lay.addWidget(self._broker_pill, 0, Qt.AlignmentFlag.AlignVCenter)

        # 10. Clock UTC ───────────────────────────────────────────────────────
        self._clock_label = QLabel("00:00:00 UTC")
        self._clock_label.setStyleSheet(
            "color:#a8b1bb; font-size:11px; font-weight:500;"
            '  font-family:"Consolas","Cascadia Code",monospace;'
            "  background:transparent; border:none;"
        )
        self._clock_label.setToolTip(tr("tooltip.clock"))
        lay.addWidget(self._clock_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # 11. HelpIcon globale ────────────────────────────────────────────────
        self._help_icon = HelpIcon(
            title=tr("help.shortcuts.title"),
            body=tr("help.shortcuts.body"),
        )
        lay.addWidget(self._help_icon, 0, Qt.AlignmentFlag.AlignVCenter)

    # ── AppState connections ──────────────────────────────────────────────────

    def _connect_state(self) -> None:
        state = AppState.instance()

        state.engine_running_changed.connect(self._on_engine_state)
        state.equity_changed.connect(self._on_equity)
        state.daily_pnl_changed.connect(self._on_pnl)
        state.open_positions_changed.connect(self._on_positions)
        state.win_rate_changed.connect(self._on_winrate)
        state.current_regime_changed.connect(self._on_regime)
        state.current_hurst_changed.connect(self._on_hurst)
        state.mode_changed.connect(self._on_mode)
        state.broker_latency_changed.connect(self._on_latency)
        state.broker_connected_changed.connect(self._on_broker_connected)
        state.current_symbol_changed.connect(self._on_current_symbol)    # Fase A.1
        state.current_scan_symbol_changed.connect(self._on_scan_symbol)  # Fase B

        # Carica valori correnti al primo render
        self._on_engine_state(state.engine_running)
        self._on_equity(state.equity)
        self._on_pnl(state.daily_pnl)
        self._on_positions(state.open_positions)
        self._on_winrate(state.win_rate)
        self._on_regime(state.current_regime)
        self._on_hurst(state.current_hurst)
        self._on_mode(state.mode)
        self._on_latency(state.broker_latency)
        self._on_broker_connected(state.broker_connected)
        self._on_current_symbol(state.current_symbol)  # Fase A.1

    # ── Slot AppState ─────────────────────────────────────────────────────────

    def _on_engine_state(self, running: bool) -> None:
        if running:
            self._engine_btn.setText(tr("topbar.stop"))
            self._engine_btn.setProperty("variant", "danger")
            self._engine_btn.setToolTip(tr("topbar.engine_stop_tip"))
        else:
            self._engine_btn.setText(tr("topbar.start"))
            self._engine_btn.setProperty("variant", "primary")
            self._engine_btn.setToolTip(tr("topbar.engine_start_tip"))
            self._scan_chip.engine_stopped()  # Fase B — nascondi chip scansione
        # Forza il refresh dello stile QSS (il property non aggiorna automaticamente)
        self._engine_btn.style().unpolish(self._engine_btn)
        self._engine_btn.style().polish(self._engine_btn)

    def _on_equity(self, value: float) -> None:
        self._equity_history.append(value)
        # Formato: 12,345.67
        formatted = f"{value:,.2f}"
        self._badge_equity.set_value(formatted)
        self._badge_equity.set_sparkline_values(list(self._equity_history))

        # Delta rispetto al primo valore della finestra
        first = list(self._equity_history)[0]
        if first and first != 0:
            delta_pct = (value - first) / first * 100.0
            self._badge_equity.set_delta(delta_pct, "%")

    def _on_pnl(self, value: float) -> None:
        prev = self._last_pnl
        self._last_pnl = value

        if value >= 0:
            color = _BULL
            formatted = f"+{value:,.2f}"
        else:
            color = _BEAR
            formatted = f"{value:,.2f}"

        self._badge_pnl.set_value(formatted)
        self._badge_pnl.set_value_color(color)

        # Flash se il valore è cambiato
        if value != prev:
            flash_color = _BULL if value > prev else _BEAR
            # Mini-flash: torna al colore PnL dopo 120ms
            self._badge_pnl.set_value_color(flash_color)
            QTimer.singleShot(
                120, lambda c=color: self._badge_pnl.set_value_color(c)
            )

    def _on_positions(self, count: int) -> None:
        self._badge_pos.set_value(f"{count}/5")

    def _on_winrate(self, rate: float) -> None:
        pct = rate * 100.0 if rate <= 1.0 else rate
        self._badge_win.set_value(f"{pct:.0f}%")
        color = _BULL if pct >= 50 else _BEAR
        self._badge_win.set_value_color(color)

    def _on_regime(self, regime: str) -> None:
        self._regime_pill.set_regime(regime, self._last_hurst)

    def _on_hurst(self, hurst: float) -> None:
        self._last_hurst = hurst
        state = AppState.instance()
        self._regime_pill.set_regime(state.current_regime, hurst)

    def _on_mode(self, mode: str) -> None:
        self._mode_pill.set_mode(mode)

    def _on_latency(self, ms: int) -> None:
        state = AppState.instance()
        self._broker_pill.update_state(state.broker_connected, ms)

    def _on_broker_connected(self, connected: bool) -> None:
        state = AppState.instance()
        self._broker_pill.update_state(connected, state.broker_latency)

    def _on_current_symbol(self, symbol_yf: str) -> None:
        """Fase A.1 — aggiorna chip simbolo con display human-readable."""
        try:
            from core.engine import INSTRUMENTS
            display = INSTRUMENTS.get(symbol_yf, (symbol_yf,))[0]
        except Exception:
            display = symbol_yf
        self._symbol_chip.setText(display)

    def _on_scan_symbol(self, symbol: str, loop_name: str) -> None:
        """Fase B — aggiorna il chip di scansione engine."""
        self._scan_chip.update_scan(symbol, loop_name)

    # ── Engine toggle ─────────────────────────────────────────────────────────

    def _toggle_engine(self) -> None:
        state = AppState.instance()
        state.engine_running = not state.engine_running

    # ── Clock ─────────────────────────────────────────────────────────────────

    def _tick_clock(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self._clock_label.setText(now.strftime("%H:%M:%S UTC"))
