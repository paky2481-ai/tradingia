"""
DashboardWorkspace — workspace MVP per il gate review (demo Qt vs Mobile).

Layout:
    QSplitter(H)
    ├── Sinistra 320px  QSplitter(V)
    │   ├── WATCHLIST   (5 righe con Sparkline + delta colorato)
    │   └── POSIZIONI   (2 righe simulate, empty-state se nessuna)
    ├── Centro (exp.)   Placeholder chart + 3 Gauge (Hurst, Kelly, Volatility)
    └── Destra 280px    Mini AI Panel (RegimePill, Gauge confidence, pred, strategy)

Demo liveness:
    QTimer 2s → aggiorna sparkline watchlist, Hurst gauge, equity via AppState.
    Mostra che il sistema è LIVE anche senza engine reale collegato.

NON modifica main_window.py — integrazione affidata a Paky.
"""
from __future__ import annotations

import random
from collections import deque
from typing import NamedTuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.i18n import tr
from gui.state.app_state import AppState
from gui.widgets.info import Gauge, HelpIcon, KPIBadge, RegimePill, Sparkline


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

_MONO_STACK   = '"Consolas", "Cascadia Code", "JetBrains Mono", monospace'
_UI_STACK     = '"Segoe UI", "Inter", "SF Pro Display", sans-serif'


# ── Dati simboli demo ────────────────────────────────────────────────────────
class _SymbolData(NamedTuple):
    symbol: str
    price: float
    delta_pct: float          # % relativo, per colorazione iniziale


_SYMBOLS: list[_SymbolData] = [
    _SymbolData("EUR/USD",  1.0872,  +0.12),
    _SymbolData("GBP/USD",  1.2701,  -0.08),
    _SymbolData("XAU/USD",  2345.50, +0.45),
    _SymbolData("S&P 500",  5282.70, +0.21),
    _SymbolData("DAX",      18730.0, -0.14),
]

# Posizioni demo (simbolo, direzione, entry, current, pnl)
_POSITIONS_DEMO = [
    ("EUR/USD", "▲", 1.0845, 1.0872, +234.50),
    ("XAU/USD", "▼", 2360.0, 2345.5, +145.00),
]

# Numero di punti sparkline per la watchlist
_SL_LEN = 50


def _random_walk(n: int, start: float, sigma: float) -> list[float]:
    """Genera una serie random walk plausibile centrata su start."""
    vals = [start]
    for _ in range(n - 1):
        vals.append(vals[-1] + random.gauss(0, sigma))
    return vals


def _make_hit_miss_history(n: int, hit_rate: float = 0.70) -> list[float]:
    """
    Genera una sequenza di n valori 0/1 con la hit_rate indicata,
    distribuita in modo non uniforme per sembrare storico reale.
    I valori usati: 0.75 per hit (> 0.5), 0.25 per miss (<= 0.5).
    Questo garantisce la visualizzazione corretta in modalita hit_miss.
    """
    result: list[float] = []
    hits_left = round(n * hit_rate)
    misses_left = n - hits_left
    for _ in range(n):
        if hits_left == 0:
            result.append(0.25)
            misses_left -= 1
        elif misses_left == 0:
            result.append(0.75)
            hits_left -= 1
        else:
            # Probabilita pesata per evitare alternanza troppo regolare
            p_hit = hits_left / (hits_left + misses_left)
            if random.random() < p_hit:
                result.append(0.75)
                hits_left -= 1
            else:
                result.append(0.25)
                misses_left -= 1
    return result


def _label(
    text: str,
    size: int = 12,
    color: str = _TEXT,
    bold: bool = False,
    mono: bool = False,
) -> QLabel:
    """Factory QLabel con stile inline."""
    lbl = QLabel(text)
    family = _MONO_STACK if mono else _UI_STACK
    weight = "700" if bold else "400"
    lbl.setStyleSheet(
        f"color:{color}; font-size:{size}px; font-weight:{weight};"
        f" font-family:{family}; background:transparent; border:none;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lbl


def _vsep() -> QFrame:
    """Linea orizzontale separatrice 1px."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background:{_BORDER_DIM}; border:none;")
    sep.setFixedHeight(1)
    return sep


def _group(title: str, min_height: int = 0) -> QGroupBox:
    """QGroupBox con stile QSS già definito in dark.qss."""
    box = QGroupBox(title)
    if min_height:
        box.setMinimumHeight(min_height)
    return box


# ═══════════════════════════════════════════════════════════════════════════
# Watchlist Demo Panel
# ═══════════════════════════════════════════════════════════════════════════

class _WatchlistPanel(QGroupBox):
    """
    Mini watchlist con 5 simboli demo.

    Ogni riga: [simbolo] [prezzo] [delta%] [Sparkline 50pt]
    Click su riga → setta AppState.current_symbol (per futura integrazione chart).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("dashboard.watchlist"), parent)
        self._rows: list[dict] = []  # [{"price_lbl", "delta_lbl", "sparkline", "data"}]

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 14, 8, 8)
        lay.setSpacing(4)

        for sym_data in _SYMBOLS:
            row_widget = self._make_row(sym_data)
            lay.addWidget(row_widget)
            if sym_data is not _SYMBOLS[-1]:
                lay.addWidget(_vsep())

        lay.addStretch(1)

    def _make_row(self, sym_data: _SymbolData) -> QWidget:
        """Costruisce una singola riga watchlist."""
        container = QWidget()
        container.setFixedHeight(34)
        container.setCursor(Qt.CursorShape.PointingHandCursor)
        container.setToolTip(tr("watchlist.row_tooltip", symbol=sym_data.symbol))

        # Sfondo hover via stylesheet dinamico
        container.setStyleSheet(
            "QWidget { background: transparent; border-radius: 4px; }"
            "QWidget:hover { background: #1c2128; }"
        )

        row = QHBoxLayout(container)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(6)

        # Simbolo
        sym_lbl = _label(sym_data.symbol, size=11, color=_TEXT, bold=True, mono=True)
        sym_lbl.setFixedWidth(62)
        row.addWidget(sym_lbl)

        # Prezzo
        price_lbl = _label(f"{sym_data.price:.4f}", size=11, color=_TEXT, mono=True)
        price_lbl.setFixedWidth(70)
        row.addWidget(price_lbl)

        # Delta %
        delta_color = _BULL if sym_data.delta_pct >= 0 else _BEAR
        sign = "+" if sym_data.delta_pct >= 0 else ""
        delta_lbl = _label(
            f"{sign}{sym_data.delta_pct:.2f}%",
            size=10, color=delta_color, mono=True
        )
        delta_lbl.setFixedWidth(52)
        row.addWidget(delta_lbl)

        # Sparkline con random walk plausibile per il simbolo
        sigma = sym_data.price * 0.0005  # sigma proporzionale al prezzo
        init_data = _random_walk(_SL_LEN, sym_data.price, sigma)
        sparkline = Sparkline(width=60, height=22)
        sparkline.set_values(init_data)
        row.addWidget(sparkline, 0, Qt.AlignmentFlag.AlignVCenter)

        # Store ref per aggiornamento live
        self._rows.append({
            "symbol": sym_data.symbol,
            "price_lbl": price_lbl,
            "delta_lbl": delta_lbl,
            "sparkline": sparkline,
            "data": deque(init_data, maxlen=_SL_LEN),
            "price": sym_data.price,
            "sigma": sigma,
        })

        # Click handler — closure su symbol
        sym_name = sym_data.symbol
        container.mousePressEvent = lambda _e, s=sym_name: self._on_click(s)

        return container

    def _on_click(self, symbol: str) -> None:
        AppState.instance().current_symbol = symbol

    def tick(self) -> None:
        """Aggiorna sparkline di una riga random (simula tick live)."""
        if not self._rows:
            return
        row = random.choice(self._rows)
        new_val = row["data"][-1] + random.gauss(0, row["sigma"])
        row["data"].append(new_val)
        row["sparkline"].set_values(list(row["data"]))

        # Aggiorna prezzo e delta riga selezionata
        current = new_val
        orig = row["price"]
        delta_pct = (current - orig) / orig * 100.0
        delta_color = _BULL if delta_pct >= 0 else _BEAR
        sign = "+" if delta_pct >= 0 else ""

        # Formato prezzo: più decimali per forex, meno per indici
        if orig < 100:
            price_str = f"{current:.4f}"
        elif orig < 10000:
            price_str = f"{current:.2f}"
        else:
            price_str = f"{current:.1f}"

        row["price_lbl"].setText(price_str)
        row["delta_lbl"].setText(f"{sign}{delta_pct:.2f}%")
        row["delta_lbl"].setStyleSheet(
            f"color:{delta_color}; font-size:10px; font-weight:400;"
            f" font-family:{_MONO_STACK}; background:transparent; border:none;"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Positions Demo Panel
# ═══════════════════════════════════════════════════════════════════════════

class _PositionsPanel(QGroupBox):
    """
    Mini panel posizioni aperte.

    Mostra 2 righe simulate. Se vuoto mostra empty-state con messaggio guida.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(tr("dashboard.positions_open"), parent)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 14, 8, 8)
        lay.setSpacing(4)

        if _POSITIONS_DEMO:
            # Header colonne
            header_lbl = QLabel(
                f"{tr('positions.header.symbol')}    {tr('positions.header.dir')}"
                f"    {tr('positions.header.entry')}    {tr('positions.header.pnl')}"
            )
            header_lbl.setStyleSheet(
                f"color:{_MUTED}; font-size:10px; font-family:{_MONO_STACK};"
                "  background:transparent; border:none; padding:2px 6px;"
            )
            lay.addWidget(header_lbl)
            lay.addWidget(_vsep())

            for pos in _POSITIONS_DEMO:
                lay.addWidget(self._make_row(*pos))
                if pos is not _POSITIONS_DEMO[-1]:
                    lay.addWidget(_vsep())
        else:
            self._add_empty_state(lay)

        lay.addStretch(1)

    def _make_row(
        self,
        symbol: str,
        direction: str,
        entry: float,
        current: float,
        pnl: float,
    ) -> QWidget:
        """Riga singola posizione: simbolo | dir | entry | current | P&L."""
        row_w = QWidget()
        row_w.setFixedHeight(30)
        row = QHBoxLayout(row_w)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(6)

        dir_color = _BULL if direction == "▲" else _BEAR
        pnl_color = _BULL if pnl >= 0 else _BEAR
        pnl_sign  = "+" if pnl >= 0 else ""

        # Direzione
        dir_lbl = _label(direction, size=13, color=dir_color, bold=True)
        dir_lbl.setFixedWidth(14)
        row.addWidget(dir_lbl)

        # Simbolo
        sym_lbl = _label(symbol, size=11, color=_TEXT, bold=True, mono=True)
        sym_lbl.setFixedWidth(62)
        row.addWidget(sym_lbl)

        # Entry → Current
        range_lbl = _label(
            f"{entry:.4f} → {current:.4f}",
            size=10, color=_MUTED, mono=True,
        )
        row.addWidget(range_lbl, 1)

        # P&L
        pnl_lbl = _label(
            f"€{pnl_sign}{pnl:.2f}",
            size=11, color=pnl_color, bold=True, mono=True,
        )
        pnl_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(pnl_lbl)

        return row_w

    def _add_empty_state(self, lay: QVBoxLayout) -> None:
        """Placeholder friendly quando nessuna posizione aperta."""
        empty = QLabel(tr("dashboard.no_positions"))
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setWordWrap(True)
        empty.setStyleSheet(
            f"color:{_MUTED}; font-size:11px; font-family:{_UI_STACK};"
            "  background:transparent; border:none; padding:12px;"
        )
        lay.addWidget(empty)


# ═══════════════════════════════════════════════════════════════════════════
# Centro: Placeholder Chart + 3 Gauge cards
# ═══════════════════════════════════════════════════════════════════════════

class _GaugeCard(QFrame):
    """
    Card compatta con Gauge + titolo + HelpIcon.
    Usata per le mini-cards sotto il placeholder chart.
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

        # Container esplicito con bordo visibile (evita override da QSS globale)
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

        title_lbl = _label(label, size=10, color=_MUTED)
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
            label="",  # label già nel titolo card
            width=160,
            height=26,
            zones=zones,
        )
        self._gauge.set_value(value)
        lay.addWidget(self._gauge, 0, Qt.AlignmentFlag.AlignCenter)

    def set_value(self, v: float) -> None:
        self._gauge.set_value(v)


class _CenterPanel(QWidget):
    """
    Area centrale: placeholder chart grande + 3 gauge card in fila.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        # ── Placeholder chart ─────────────────────────────────────────────
        self._chart_placeholder = QFrame()
        self._chart_placeholder.setObjectName("ChartPlaceholder")
        self._chart_placeholder.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._chart_placeholder.setStyleSheet(
            "#ChartPlaceholder {"
            f"  background:{_BG_BASE};"
            f"  border:1px solid {_BORDER};"
            "  border-radius:6px;"
            "}"
        )

        ph_lay = QVBoxLayout(self._chart_placeholder)
        ph_lay.setContentsMargins(0, 0, 0, 0)
        ph_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        chart_main = QLabel(tr("dashboard.chart_placeholder"))
        chart_main.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_main.setStyleSheet(
            f"color:{_MUTED}; font-size:22px; font-weight:300;"
            f" font-family:{_UI_STACK}; background:transparent; border:none;"
            "  letter-spacing:3px;"
        )
        ph_lay.addWidget(chart_main)

        chart_sub = QLabel(tr("dashboard.chart_subtitle"))
        chart_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_sub.setStyleSheet(
            f"color:#30363d; font-size:12px; font-weight:400;"
            f" font-family:{_UI_STACK}; background:transparent; border:none;"
        )
        ph_lay.addWidget(chart_sub)

        outer.addWidget(self._chart_placeholder, 1)

        # ── Riga di 3 Gauge cards ─────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(6)

        self._hurst_card = _GaugeCard(
            label=tr("gauge.hurst"),
            help_title="Hurst Exponent",
            help_body=tr("help.hurst.body"),
            value=0.62,
        )
        cards_row.addWidget(self._hurst_card)

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
        cards_row.addWidget(self._kelly_card)

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
        cards_row.addWidget(self._vol_card)

        outer.addLayout(cards_row)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_hurst(self, v: float) -> None:
        self._hurst_card.set_value(v)

    def set_kelly(self, v: float) -> None:
        self._kelly_card.set_value(v)

    def set_volatility(self, v: float) -> None:
        self._vol_card.set_value(v)


# ═══════════════════════════════════════════════════════════════════════════
# Destra: Mini AI Panel
# ═══════════════════════════════════════════════════════════════════════════

class _AIPanel(QGroupBox):
    """
    Mini AI analysis panel per il gate review.

    Mostra: RegimePill, Gauge confidence, predizione corrente,
    sparkline storia predizioni (hit_miss mode), strategy footer.

    Fix applicati:
      8 — QGroupBox titolo senza separatori/border-top spurii (margin solo nel QSS)
      9 — Predizione come singolo QLabel RichText (no layout a 2 colonne)
     10 — Strategy/signal in footer QFrame pinned in fondo
     11 — History sparkline in modalita hit_miss con dati demo 70% accuracy
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("AI ANALYSIS", parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setFixedWidth(280)

        # Fix 8: margin-top 18px lascia spazio al titolo QGroupBox senza
        # aggiungere separatori espliciti. Nessun QFrame HLine prima del pill.
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 18, 8, 0)
        lay.setSpacing(8)

        # RegimePill — valori iniziali da AppState (nessun hard-code)
        self._regime_pill = RegimePill()
        _init_state = AppState.instance()
        self._regime_pill.set_regime(
            _init_state.current_regime or "unknown",
            _init_state.current_hurst,
        )
        lay.addWidget(self._regime_pill, 0, Qt.AlignmentFlag.AlignLeft)

        # Gauge Confidence + HelpIcon
        conf_header = QHBoxLayout()
        conf_header.setContentsMargins(0, 0, 0, 0)
        conf_header.setSpacing(4)
        conf_lbl = _label(tr("dashboard.confidence"), size=10, color=_MUTED)
        conf_lbl.setStyleSheet(
            f"color:{_MUTED}; font-size:10px; font-weight:600;"
            f" font-family:{_UI_STACK}; text-transform:uppercase;"
            "  background:transparent; border:none; letter-spacing:0.4px;"
        )
        conf_header.addWidget(conf_lbl)
        conf_header.addWidget(
            HelpIcon(
                tr("dashboard.ai_prediction"),
                tr("help.confidence.body"),
            )
        )
        conf_header.addStretch(1)
        lay.addLayout(conf_header)

        self._conf_gauge = Gauge(
            label="",
            width=240,
            height=26,
            zones=[
                (0.0, 0.5, _BEAR),
                (0.5, 0.7, _WARN),
                (0.7, 1.0, _BULL),
            ],
        )
        self._conf_gauge.set_value(0.78)
        lay.addWidget(self._conf_gauge, 0, Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(_vsep())

        # Fix 9: predizione corrente come singolo QLabel RichText.
        # Icona ▲, testo "LONG", sottotitolo "AI Prediction" su una riga compatta.
        self._pred_label = QLabel(
            '<span style="color:#3fb950;font-size:18px;">▲</span>'
            '&nbsp;<b style="color:#3fb950;font-size:14px;">LONG</b>'
            f'&nbsp;<span style="color:#a8b1bb;font-size:10px;">{tr("dashboard.ai_prediction")}</span>'
        )
        self._pred_label.setTextFormat(Qt.TextFormat.RichText)
        self._pred_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pred_label.setStyleSheet("background:transparent; border:none;")
        lay.addWidget(self._pred_label)

        lay.addWidget(_vsep())

        # Sparkline storia predizioni
        spark_header = _label(tr("dashboard.history"), size=9, color=_MUTED)
        spark_header.setStyleSheet(
            f"color:{_MUTED}; font-size:9px; font-weight:600;"
            f" font-family:{_UI_STACK}; text-transform:uppercase;"
            "  background:transparent; border:none; letter-spacing:0.4px;"
        )
        lay.addWidget(spark_header)

        # Fix 11: sparkline in hit_miss mode con ~70% accuracy demo.
        # Sequenza realistica: 70 hit / 30 miss su 50 campioni, distribuiti
        # in modo non uniforme per sembrare dati reali (non alterni regolari).
        self._pred_sparkline = Sparkline(width=240, height=28, marker_mode="hit_miss")
        pred_history = _make_hit_miss_history(_SL_LEN, hit_rate=0.70)
        self._pred_sparkline.set_values(pred_history)
        lay.addWidget(self._pred_sparkline)

        # Stretch spinge il footer in fondo
        lay.addStretch(1)

        # Fix 10: footer pinned in fondo con bordo top e sfondo leggermente
        # diverso dal pannello. Strategy + last signal dentro al footer.
        footer = QFrame()
        footer.setStyleSheet(
            f"background:{_BG_BASE};"
            f"border-top:1px solid {_BORDER};"
            "border-radius:0px;"
            "padding:0px;"
        )
        footer_lay = QVBoxLayout(footer)
        footer_lay.setContentsMargins(6, 6, 6, 6)
        footer_lay.setSpacing(2)

        self._strategy_lbl = QLabel(f"{tr('dashboard.strategy_label')} Trend4H")
        self._strategy_lbl.setStyleSheet(
            f"font-size:9px; color:{_TEXT}; font-family:{_UI_STACK};"
            "  background:transparent; border:none;"
        )
        footer_lay.addWidget(self._strategy_lbl)

        self._signal_lbl = QLabel(tr("dashboard.last_signal", n=4))
        self._signal_lbl.setStyleSheet(
            f"font-size:9px; color:{_MUTED}; font-family:{_UI_STACK};"
            "  background:transparent; border:none;"
        )
        footer_lay.addWidget(self._signal_lbl)

        lay.addWidget(footer)

        # Store per tick demo
        self._pred_data: deque[float] = deque(pred_history, maxlen=_SL_LEN)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def tick_pred(self) -> None:
        """Aggiunge un punto predizione demo (simulazione live).

        In modalita hit_miss i valori demo sono 0.75 (hit) o 0.25 (miss)
        con probabilita ~70% hit — coerente con i dati iniziali.
        """
        # Fix 11: i tick demo usano valori 0.75/0.25 coerenti con hit_miss
        if random.random() < 0.70:
            new_val = 0.75  # hit
        else:
            new_val = 0.25  # miss
        self._pred_data.append(new_val)
        self._pred_sparkline.set_values(list(self._pred_data))

        # Fix 9: aggiorna RichText mantenendo il formato icona+testo+sottotitolo
        if new_val > 0.5:
            icon_char = "▲"
            color = _BULL
            direction = "LONG"
        else:
            icon_char = "▼"
            color = _BEAR
            direction = "SHORT"
        self._pred_label.setText(
            f'<span style="color:{color};font-size:18px;">{icon_char}</span>'
            f'&nbsp;<b style="color:{color};font-size:14px;">{direction}</b>'
            f'&nbsp;<span style="color:#a8b1bb;font-size:10px;">{tr("dashboard.ai_prediction")}</span>'
        )

    def update_regime(self, regime: str, hurst: float) -> None:
        self._regime_pill.set_regime(regime, hurst)

    def update_confidence(self, v: float) -> None:
        self._conf_gauge.set_value(v)


# ═══════════════════════════════════════════════════════════════════════════
# DashboardWorkspace — root widget
# ═══════════════════════════════════════════════════════════════════════════

class DashboardWorkspace(QWidget):
    """
    Workspace principale per il gate review.

    Layout: QSplitter(H) → [sinistra 320] [centro exp.] [destra 280]

    Demo liveness: QTimer 2s simula tick live su watchlist, AI panel e
    AppState.equity — dimostra reattività del sistema.

    Uso in MainWindow (a cura di Paky):
        ws = DashboardWorkspace()
        stack.addWidget(ws)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Inizializza AppState demo
        state = AppState.instance()
        if state.equity == 0.0:
            state._equity = 10_000.0   # seed senza emettere signal (no history flash)
        state.broker_connected = True
        state.broker_latency = 23
        state.win_rate = 0.67
        state.open_positions = len(_POSITIONS_DEMO)
        state.current_regime = "trending"
        state.current_hurst = 0.62
        state.mode = "paper"

        # ── Layout radice ─────────────────────────────────────────────────
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)
        root.addWidget(splitter)

        # ── Sinistra: splitter verticale ──────────────────────────────────
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        left_splitter.setMinimumWidth(260)
        left_splitter.setMaximumWidth(380)
        left_splitter.setHandleWidth(2)

        self._watchlist = _WatchlistPanel()
        left_splitter.addWidget(self._watchlist)

        self._positions = _PositionsPanel()
        left_splitter.addWidget(self._positions)

        left_splitter.setStretchFactor(0, 3)
        left_splitter.setStretchFactor(1, 1)
        left_splitter.setSizes([320, 180])

        splitter.addWidget(left_splitter)

        # ── Centro: chart placeholder + gauge cards ────────────────────────
        self._center = _CenterPanel()
        splitter.addWidget(self._center)

        # ── Destra: AI panel ──────────────────────────────────────────────
        self._ai_panel = _AIPanel()
        splitter.addWidget(self._ai_panel)

        splitter.setStretchFactor(0, 0)   # sinistra: dimensione fissa
        splitter.setStretchFactor(1, 1)   # centro: espandibile
        splitter.setStretchFactor(2, 0)   # destra: dimensione fissa
        splitter.setSizes([320, 800, 280])

        # ── Demo liveness timer ───────────────────────────────────────────
        self._demo_hurst: float = 0.62
        self._demo_equity: float = 10_000.0
        self._tick_count: int = 0

        self._demo_timer = QTimer(self)
        self._demo_timer.timeout.connect(self._demo_tick)
        self._demo_timer.start(2000)  # 2 secondi

    # ── Demo tick ─────────────────────────────────────────────────────────────

    def _demo_tick(self) -> None:
        """
        Simula un tick live ogni 2 secondi.
        Aggiorna: watchlist sparkline, Hurst gauge, equity via AppState,
        AI panel predizioni — dimostra il sistema è LIVE.
        """
        self._tick_count += 1
        state = AppState.instance()

        # 1. Watchlist: aggiorna 1-2 simboli random
        self._watchlist.tick()
        if self._tick_count % 2 == 0:
            self._watchlist.tick()

        # 2. AI panel: nuovo punto predizione
        self._ai_panel.tick_pred()

        # 3. Hurst drift lento ±0.02 — unica sorgente di verità via AppState
        self._demo_hurst += random.uniform(-0.02, 0.02)
        self._demo_hurst = max(0.2, min(0.85, self._demo_hurst))
        self._center.set_hurst(self._demo_hurst)
        state.current_hurst = round(self._demo_hurst, 4)

        # Regime determinato centralmente e scritto in AppState
        if self._demo_hurst > 0.6:
            regime = "trending"
        elif self._demo_hurst < 0.4:
            regime = "cycling"
        else:
            regime = "choppy"
        state.current_regime = regime

        # AI panel legge da AppState (nessun random indipendente)
        self._ai_panel.update_regime(state.current_regime, state.current_hurst)

        # 4. Equity random walk → AppState (triggera TopBar via signal)
        delta = random.gauss(5.0, 40.0)
        self._demo_equity += delta
        state.equity = round(self._demo_equity, 2)

        # 5. P&L giornaliero
        state.daily_pnl = round(self._demo_equity - 10_000.0, 2)

        # 6. Latency jitter (simula connessione reale)
        if self._tick_count % 5 == 0:
            state.broker_latency = random.randint(18, 85)
