"""
DashboardWorkspace — Cruscotto principale.

Layout Bloomberg-style (Max, 2026-05-18):

    QHBoxLayout(root)
    +-- WatchlistPanel  280-360px  (sempre visibile, fuori dai tab)
    +-- right_container (QWidget)
        +-- _ChartArea    stretch=50  (placeholder/futuro CandlestickChart)
        +-- _GaugeStrip   ~80px fissi (3 gauge: Hurst/Kelly/Volatility)
        +-- QTabWidget    stretch=50  (2 macro-tab: Trading / Analisi)
              ├── Tab "Trading"  → QSplitter H [PositionsPanel | EnginePanel]
              └── Tab "Analisi"  → QSplitter H [AIAnalysisPanel | PortfolioPanel]

Vincoli layout:
    - Tab attivo occupa almeno 50% altezza verticale (stretch 50/50 con chart)
    - Ogni macro-tab mostra 2 panel affiancati 50/50 in QSplitter orizzontale
    - Un solo macro-tab visibile alla volta (default QTabWidget)

Demo liveness:
    QTimer 2s simula AppState per variabili senza emit dal core.
    NON sovrascrive segnali Fase 5 (ai_result, kelly_update,
    regime_update, loop_heartbeat, correlation_update).

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState
from gui.widgets.info import Gauge, HelpIcon

# Panel atomici
from gui.panels.watchlist_panel import WatchlistPanel
from gui.panels.positions_panel import PositionsPanel
from gui.panels.ai_analysis_panel import AIAnalysisPanel
from gui.panels.engine_panel import EnginePanel
from gui.panels.portfolio_panel import PortfolioPanel


# ── Palette (coerente con dark.qss) ─────────────────────────────────────────
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

_UI_STACK     = '"Segoe UI", "Inter", "SF Pro Display", sans-serif'

# ── Chiavi i18n dei 2 macro-tab (usate in _apply_i18n) ───────────────────────
_TAB_KEYS = [
    "workspace.tab_trading",
    "workspace.tab_analysis",
]


def _label(
    text: str,
    size: int = 12,
    color: str = _TEXT,
    bold: bool = False,
) -> QLabel:
    """Factory QLabel con stile inline."""
    lbl = QLabel(text)
    weight = "700" if bold else "400"
    lbl.setStyleSheet(
        f"color:{color}; font-size:{size}px; font-weight:{weight};"
        f" font-family:{_UI_STACK}; background:transparent; border:none;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lbl


# ═══════════════════════════════════════════════════════════════════════════
# _GaugeCard — singola card con Gauge + titolo + HelpIcon
# ═══════════════════════════════════════════════════════════════════════════

class _GaugeCard(QFrame):
    """
    Card compatta con Gauge + titolo + HelpIcon.
    Altezza fissa per non dilatare la strip.
    """

    def __init__(
        self,
        label: str,
        help_title: str,
        help_body: str,
        value: float,
        zones: list[tuple[float, float, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GaugeCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Container con bordo visibile
        inner_frame = QFrame(self)
        inner_frame.setStyleSheet(
            "background:#161b22;"
            "border:1px solid #30363d;"
            "border-radius:4px;"
            "padding:4px;"
        )

        lay = QVBoxLayout(inner_frame)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        outer.addWidget(inner_frame)

        # Riga titolo + help icon
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)

        title_lbl = QLabel(label)
        title_lbl.setStyleSheet(
            f"color:{_MUTED}; font-size:10px; font-weight:600;"
            f" font-family:{_UI_STACK}; text-transform:uppercase;"
            "  background:transparent; border:none; letter-spacing:0.4px;"
        )
        header.addWidget(title_lbl)
        header.addWidget(HelpIcon(help_title, help_body))
        header.addStretch(1)
        lay.addLayout(header)

        # Gauge
        self._gauge = Gauge(
            label="",
            width=160,
            height=26,
            zones=zones,
        )
        self._gauge.set_value(value)
        lay.addWidget(self._gauge, 0, Qt.AlignmentFlag.AlignCenter)

    def set_value(self, v: float) -> None:
        self._gauge.set_value(v)


# ═══════════════════════════════════════════════════════════════════════════
# _ChartArea — placeholder chart (futuro CandlestickChart)
# ═══════════════════════════════════════════════════════════════════════════

class _ChartArea(QFrame):
    """
    Area chart: per ora placeholder grafico.
    Quando CandlestickChart sarà pronto, basterà
    sostituire il contenuto di ph_lay senza toccare
    il layout esterno (DashboardWorkspace).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChartPlaceholder")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "#ChartPlaceholder {"
            f"  background:{_BG_BASE};"
            f"  border:1px solid {_BORDER};"
            "  border-radius:6px;"
            "}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        chart_main = QLabel(tr("dashboard.chart_placeholder"))
        chart_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_main.setStyleSheet(
            f"color:{_MUTED}; font-size:22px; font-weight:300;"
            f" font-family:{_UI_STACK}; background:transparent; border:none;"
            "  letter-spacing:3px;"
        )
        lay.addWidget(chart_main)

        chart_sub = QLabel(tr("dashboard.chart_subtitle"))
        chart_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_sub.setStyleSheet(
            f"color:#30363d; font-size:12px; font-weight:400;"
            f" font-family:{_UI_STACK}; background:transparent; border:none;"
        )
        lay.addWidget(chart_sub)


# ═══════════════════════════════════════════════════════════════════════════
# _GaugeStrip — 3 gauge orizzontali in strip sticky a ~80px
# ═══════════════════════════════════════════════════════════════════════════

class _GaugeStrip(QWidget):
    """
    Striscia orizzontale con 3 GaugeCard (Hurst / Kelly / Volatility).
    Altezza fissa ~80px — non si dilata.
    API: set_hurst(), set_kelly(), set_volatility().
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(82)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(6)

        self._hurst_card = _GaugeCard(
            label=tr("gauge.hurst"),
            help_title="Hurst Exponent",
            help_body=tr("help.hurst.body"),
            value=0.62,
        )
        row.addWidget(self._hurst_card)

        self._kelly_card = _GaugeCard(
            label=tr("gauge.kelly"),
            help_title="Kelly %",
            help_body=tr("help.kelly.body"),
            value=0.023,
            zones=[
                (0.0,  0.05, _BULL),
                (0.05, 0.10, _WARN),
                (0.10, 1.00, _BEAR),
            ],
        )
        row.addWidget(self._kelly_card)

        self._vol_card = _GaugeCard(
            label=tr("gauge.volatility"),
            help_title="Volatility (ATR Percentile)",
            help_body=tr("help.volatility.body"),
            value=0.45,
            zones=[
                (0.0, 0.3,  _INFO_LIGHT),
                (0.3, 0.7,  _BULL),
                (0.7, 1.0,  _WARN),
            ],
        )
        row.addWidget(self._vol_card)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_hurst(self, v: float) -> None:
        self._hurst_card.set_value(v)

    def set_kelly(self, v: float) -> None:
        self._kelly_card.set_value(v)

    def set_volatility(self, v: float) -> None:
        self._vol_card.set_value(v)


# ═══════════════════════════════════════════════════════════════════════════
# DashboardWorkspace — root widget
# ═══════════════════════════════════════════════════════════════════════════

class DashboardWorkspace(QWidget):
    """
    Workspace principale Cruscotto — layout Bloomberg-style.

    Struttura:
        QHBoxLayout
        ├── WatchlistPanel  (280-360px, sempre visibile)
        └── right_container (QWidget, espandibile)
            ├── _ChartArea     (stretch=65)
            ├── _GaugeStrip    (80px fissi)
            └── QTabWidget     (stretch=50)
                ├── QSplitter H [PositionsPanel | EnginePanel]     [0] Trading
                └── QSplitter H [AIAnalysisPanel | PortfolioPanel] [1] Analisi

    Uso in MainWindow (a cura di Paky):
        ws = DashboardWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Inizializza AppState demo (solo variabili senza emit dal core)
        state = AppState.instance()
        if state.equity == 0.0:
            state._equity = 10_000.0   # seed senza emettere signal
        state.broker_connected = True
        state.broker_latency = 23
        state.win_rate = 0.67
        state.current_regime = "trending"
        state.current_hurst = 0.62
        state.mode = "paper"

        # ── Layout radice ─────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Splitter principale: watchlist | right
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(2)
        root.addWidget(main_splitter)

        # ── Sinistra: WatchlistPanel (sempre visibile) ─────────────────────
        self._watchlist = WatchlistPanel()
        self._watchlist.setMinimumWidth(280)
        self._watchlist.setMaximumWidth(360)
        main_splitter.addWidget(self._watchlist)

        # ── Destra: chart + gauge strip + tab widget ───────────────────────
        right_container = QWidget()
        right_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_col = QVBoxLayout(right_container)
        right_col.setContentsMargins(6, 0, 0, 0)
        right_col.setSpacing(6)

        # 1. Area chart (50% altezza — parità con tab widget)
        self._chart_area = _ChartArea()
        right_col.addWidget(self._chart_area, stretch=50)

        # 2. Gauge strip (altezza fissa 82px)
        self._gauge_strip = _GaugeStrip()
        right_col.addWidget(self._gauge_strip, stretch=0)

        # 3. QTabWidget con 2 macro-tab (50% altezza — almeno 50% schermo)
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self._tab_widget.setMovable(False)
        self._tab_widget.setStyleSheet(
            "QTabWidget::pane {"
            f"  border: 1px solid {_BORDER};"
            f"  background: {_BG_SURFACE};"
            "}"
            "QTabBar::tab {"
            f"  background: {_BG_ELEVATED};"
            f"  color: {_MUTED};"
            "  padding: 5px 14px;"
            "  font-size: 11px;"
            f"  font-family: {_UI_STACK};"
            f"  border: 1px solid {_BORDER_DIM};"
            "  border-bottom: none;"
            "  margin-right: 2px;"
            "}"
            "QTabBar::tab:selected {"
            f"  background: {_BG_SURFACE};"
            f"  color: {_TEXT};"
            f"  border-color: {_BORDER};"
            "}"
            "QTabBar::tab:hover:!selected {"
            f"  color: {_TEXT};"
            "}"
        )

        # Panel atomici (attributi esposti per accesso esterno)
        self._positions = PositionsPanel()
        self._engine = EnginePanel()
        self._ai_panel = AIAnalysisPanel()
        self._portfolio = PortfolioPanel()

        # Macro-tab 0: Trading — Posizioni + Engine affiancati 50/50
        trading_split = QSplitter(Qt.Orientation.Horizontal)
        trading_split.addWidget(self._positions)
        trading_split.addWidget(self._engine)
        trading_split.setSizes([500, 500])
        trading_split.setHandleWidth(2)

        # Macro-tab 1: Analisi — AI Analysis + Portfolio affiancati 50/50
        analysis_split = QSplitter(Qt.Orientation.Horizontal)
        analysis_split.addWidget(self._ai_panel)
        analysis_split.addWidget(self._portfolio)
        analysis_split.setSizes([500, 500])
        analysis_split.setHandleWidth(2)

        self._tab_widget.addTab(trading_split,  tr("workspace.tab_trading"))
        self._tab_widget.addTab(analysis_split, tr("workspace.tab_analysis"))
        self._tab_widget.setCurrentIndex(0)   # Trading di default

        right_col.addWidget(self._tab_widget, stretch=50)

        main_splitter.addWidget(right_container)
        main_splitter.setSizes([320, 1100])
        main_splitter.setStretchFactor(0, 0)   # watchlist: fissa
        main_splitter.setStretchFactor(1, 1)   # destra: espandibile

        # ── i18n dinamico: aggiorna nomi tab a cambio lingua ──────────────
        try:
            from gui.state.signal_bus import SignalBus
            SignalBus.instance().language_changed.connect(self._apply_i18n)
        except Exception:
            pass  # bus non ancora disponibile in test headless

        # ── Demo liveness timer ───────────────────────────────────────────
        # Simula variabili AppState che non hanno ancora emit dal core engine.
        # NON tocca: ai_result, kelly_update, regime_update, loop_heartbeat,
        # correlation_update — quelli sono di competenza del SignalBus Fase 5.
        self._demo_hurst: float = 0.62
        self._demo_equity: float = 10_000.0
        self._tick_count: int = 0

        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_timer.start(2000)

    # ── i18n ─────────────────────────────────────────────────────────────────

    def _apply_i18n(self) -> None:
        """Aggiorna i testi dei 2 macro-tab quando cambia la lingua."""
        for idx, key in enumerate(_TAB_KEYS):
            self._tab_widget.setTabText(idx, tr(key))

    # ── Demo tick ─────────────────────────────────────────────────────────────

    def _demo_tick(self) -> None:
        """
        Simula un tick live ogni 2 secondi per variabili senza emit core.
        Aggiorna: Hurst gauge strip, equity, daily_pnl, latency via AppState.

        NON chiama metodi update_*() diretti sui panel atomici — quelli
        ascoltano gia' il SignalBus in autonomia.
        """
        self._tick_count += 1
        state = AppState.instance()

        # 1. Hurst drift lento — aggiorna le 3 gauge nella strip
        self._demo_hurst += random.uniform(-0.02, 0.02)
        self._demo_hurst = max(0.2, min(0.85, self._demo_hurst))
        self._gauge_strip.set_hurst(self._demo_hurst)
        state.current_hurst = round(self._demo_hurst, 4)

        # Regime determinato da Hurst e scritto in AppState
        # (NON emette regime_update sul bus — e' simulazione locale)
        if self._demo_hurst > 0.6:
            state.current_regime = "trending"
        elif self._demo_hurst < 0.4:
            state.current_regime = "cycling"
        else:
            state.current_regime = "choppy"

        # 2. Equity random walk → AppState (triggera TopBar via signal)
        delta = random.gauss(5.0, 40.0)
        self._demo_equity += delta
        state.equity = round(self._demo_equity, 2)

        # 3. P&L giornaliero
        state.daily_pnl = round(self._demo_equity - 10_000.0, 2)

        # 4. Latency jitter ogni 5 tick
        if self._tick_count % 5 == 0:
            state.broker_latency = random.randint(18, 85)
