"""
DashboardWorkspace — Cruscotto principale (trader puro).

Layout Bloomberg-style (Fase A, 2026-05-18):

    QHBoxLayout(root)
    +-- WatchlistPanel       280-360px  (sempre visibile)
    +-- right_container (QWidget)
        +-- _ChartArea         stretch=1  (DOMINANTE — occupa tutta l'altezza residua)
        +-- _GaugeStrip        ~82px fissi (3 gauge: Hurst/Kelly/Volatility)
        +-- _FundamentalsStrip ~36px fissi (P/E | Mkt Cap | Div | Beta per symbol)

Posizioni + Engine spostati in OrderTicketWorkspace (workspace "Operativo", Ctrl+2).

Demo liveness:
    QTimer 2s simula AppState per variabili senza emit dal core.
    NON sovrascrive segnali Fase 5.

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

import asyncio
import random

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState
from gui.widgets.info import Gauge, HelpIcon

# Panel atomici
from gui.panels.watchlist_panel import WatchlistPanel


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
# _FundamentalsStrip — strip compatta con P/E, Mkt Cap, Div, Beta
# ═══════════════════════════════════════════════════════════════════════════

class _FundamentalsStrip(QWidget):
    """
    Striscia orizzontale compatta ~36px con label fondamentali per current_symbol.

    Layout: [Label simbolo] P/E: 15.2 | Mkt Cap: $2.5T | Div: 0.5% | Beta: 1.21

    Ascolta AppState.current_symbol_changed. Quando il simbolo cambia
    chiama fundamental_feed.get_fundamentals() in asyncio.
    Se i dati non sono disponibili (forex, error), mostra "—".
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(36)
        self.setStyleSheet(
            f"background:{_BG_SURFACE};"
            f"border-top:1px solid {_BORDER_DIM};"
            f"border-bottom:1px solid {_BORDER_DIM};"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(0)

        # Label simbolo (grigio scuro, aggiornato su cambio symbol)
        self._sym_lbl = QLabel("—")
        self._sym_lbl.setStyleSheet(
            f"color:{_ACCENT}; font-size:11px; font-weight:700;"
            f" font-family:{_UI_STACK}; background:transparent; border:none;"
            "  min-width:70px;"
        )
        row.addWidget(self._sym_lbl)

        # Separatore
        sep0 = QLabel("|")
        sep0.setStyleSheet(f"color:{_BORDER}; background:transparent; border:none; padding:0 6px;")
        row.addWidget(sep0)

        # P/E
        pe_title = QLabel(tr("dashboard.fund_pe") + ":")
        pe_title.setStyleSheet(self._label_style(_MUTED))
        row.addWidget(pe_title)
        self._pe_lbl = QLabel(tr("dashboard.fund_na"))
        self._pe_lbl.setStyleSheet(self._label_style(_TEXT))
        row.addWidget(self._pe_lbl)

        row.addWidget(self._sep())

        # Mkt Cap
        mc_title = QLabel(tr("dashboard.fund_mktcap") + ":")
        mc_title.setStyleSheet(self._label_style(_MUTED))
        row.addWidget(mc_title)
        self._mc_lbl = QLabel(tr("dashboard.fund_na"))
        self._mc_lbl.setStyleSheet(self._label_style(_TEXT))
        row.addWidget(self._mc_lbl)

        row.addWidget(self._sep())

        # Div yield
        div_title = QLabel(tr("dashboard.fund_div") + ":")
        div_title.setStyleSheet(self._label_style(_MUTED))
        row.addWidget(div_title)
        self._div_lbl = QLabel(tr("dashboard.fund_na"))
        self._div_lbl.setStyleSheet(self._label_style(_TEXT))
        row.addWidget(self._div_lbl)

        row.addWidget(self._sep())

        # Beta
        beta_title = QLabel(tr("dashboard.fund_beta") + ":")
        beta_title.setStyleSheet(self._label_style(_MUTED))
        row.addWidget(beta_title)
        self._beta_lbl = QLabel(tr("dashboard.fund_na"))
        self._beta_lbl.setStyleSheet(self._label_style(_TEXT))
        row.addWidget(self._beta_lbl)

        row.addStretch(1)

        # Collega cambio simbolo
        try:
            AppState.instance().current_symbol_changed.connect(self._on_symbol_changed)
            # Popola subito con il simbolo corrente
            self._on_symbol_changed(AppState.instance().current_symbol)
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _label_style(color: str) -> str:
        return (
            f"color:{color}; font-size:11px; font-weight:400;"
            f" font-family:{_UI_STACK}; background:transparent; border:none;"
            "  padding-left:4px; padding-right:4px;"
        )

    @staticmethod
    def _sep() -> QLabel:
        lbl = QLabel("|")
        lbl.setStyleSheet(
            f"color:{_BORDER}; background:transparent; border:none; padding:0 4px;"
        )
        return lbl

    # ── Slot ──────────────────────────────────────────────────────────────────

    def _on_symbol_changed(self, symbol: str) -> None:
        """Aggiorna label simbolo e avvia fetch fondamentali async."""
        self._sym_lbl.setText(symbol)
        self._reset_labels()
        # Fetch asincrono
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._fetch_fundamentals(symbol))
            else:
                # In test headless il loop non gira — nessun fetch
                pass
        except Exception:
            pass  # loop non disponibile in test headless

    def _reset_labels(self) -> None:
        na = tr("dashboard.fund_na")
        self._pe_lbl.setText(na)
        self._mc_lbl.setText(na)
        self._div_lbl.setText(na)
        self._beta_lbl.setText(na)

    async def _fetch_fundamentals(self, symbol: str) -> None:
        """Chiede dati a fundamental_feed; se fallisce lascia '—'."""
        try:
            from data.fundamental.fundamental_feed import get_fundamentals
            data = await get_fundamentals(symbol)
            if data is None:
                return
            na = tr("dashboard.fund_na")
            pe    = data.get("pe_ratio")
            mc    = data.get("market_cap")
            div   = data.get("dividend_yield")
            beta  = data.get("beta")

            self._pe_lbl.setText(f"{pe:.1f}"  if pe   is not None else na)
            self._mc_lbl.setText(_fmt_mktcap(mc) if mc is not None else na)
            self._div_lbl.setText(f"{div:.2f}%" if div is not None else na)
            self._beta_lbl.setText(f"{beta:.2f}" if beta is not None else na)
        except Exception:
            pass  # fundamental_feed non disponibile o fetch fallito


def _fmt_mktcap(v: float) -> str:
    """Formatta market cap come $1.2T / $345B / $12M."""
    if v >= 1e12:
        return f"${v/1e12:.1f}T"
    if v >= 1e9:
        return f"${v/1e9:.0f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:.0f}"


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
            ├── _ChartArea         (stretch=1 — DOMINANTE)
            ├── _GaugeStrip        (82px fissi)
            └── _FundamentalsStrip (36px fissi)

    Posizioni + Engine sono nel workspace "Operativo" (Ctrl+2).

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

        # ── Destra: chart + gauge strip + fundamentals + tab widget ───────
        right_container = QWidget()
        right_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_col = QVBoxLayout(right_container)
        right_col.setContentsMargins(6, 0, 0, 0)
        right_col.setSpacing(4)

        # 1. Area chart — DOMINANTE: stretch=1 occupa tutto lo spazio verticale residuo
        self._chart_area = _ChartArea()
        right_col.addWidget(self._chart_area, stretch=1)

        # 2. Gauge strip (altezza fissa 82px)
        self._gauge_strip = _GaugeStrip()
        right_col.addWidget(self._gauge_strip, stretch=0)

        # 3. Fundamentals strip (altezza fissa 36px)
        self._fundamentals = _FundamentalsStrip()
        right_col.addWidget(self._fundamentals, stretch=0)

        main_splitter.addWidget(right_container)
        main_splitter.setSizes([320, 1100])
        main_splitter.setStretchFactor(0, 0)   # watchlist: fissa
        main_splitter.setStretchFactor(1, 1)   # destra: espandibile

        # ── Demo liveness timer ───────────────────────────────────────────
        # Simula variabili AppState che non hanno ancora emit dal core engine.
        # NON tocca: ai_result, kelly_update, regime_update, loop_heartbeat,
        # correlation_update — quelli sono di competenza del SignalBus Fase 5.
        self._demo_hurst: float = 0.62
        self._demo_equity: float = 10_000.0
        self._demo_kelly: float = 0.023
        self._demo_vol: float = 0.45
        self._tick_count: int = 0

        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_timer.start(2000)

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

        # 5. Kelly drift (simulazione finche' RiskManager non emette kelly_update)
        self._demo_kelly += random.uniform(-0.003, 0.003)
        self._demo_kelly = max(0.0, min(0.12, self._demo_kelly))
        self._gauge_strip.set_kelly(self._demo_kelly)

        # 6. Volatility drift (ATR percentile simulato)
        self._demo_vol += random.uniform(-0.02, 0.02)
        self._demo_vol = max(0.05, min(0.95, self._demo_vol))
        self._gauge_strip.set_volatility(self._demo_vol)
