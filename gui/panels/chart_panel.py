"""
Chart Panel
Hosts the CandlestickChart and a top info bar with symbol/price/change info.

Fase D (2026-05-20):
    - Selettore timeframe (1H / 4H / 1D / 1W) + selettore periodo (3M / 1A / 5A / MAX)
      in una striscia dedicata (28px) tra info bar e MA legend.
    - ChartPanel autonomo: gestisce fetch OHLCV internamente via asyncio.ensure_future.
      Ascolta AppState.current_symbol_changed e ri-fetcha ad ogni cambio TF/periodo.
    - Default: 1H + 1A.
    - Pattern asyncio identico a _FundamentalsStrip in dashboard.py.

Fase D — loading feedback (2026-05-20):
    - StatusDot nella selector bar: "loading" durante il fetch, "idle" a riposo, "error" su fail.
    - _empty_label aggiornata con testo contestuale (downloading / errore / vuoto).
"""

from __future__ import annotations

import asyncio
from typing import Optional
import pandas as pd

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy,
)

from gui.widgets.candlestick_chart import CandlestickChart
from gui.widgets.oscillator_chart import OscillatorChart
from gui.widgets.info import StatusDot
from gui.i18n import tr


# ── Mapping TF label → feed timeframe ────────────────────────────────────────
_TF_MAP: dict[str, str] = {
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
    "1W": "1w",
}

# ── Barre approssimate per giorno per ogni timeframe ─────────────────────────
_BARS_PER_DAY: dict[str, float] = {
    "1H": 24.0,
    "4H": 6.0,
    "1D": 1.0,
    "1W": 1.0 / 7.0,
}

# ── Giorni per ogni periodo ───────────────────────────────────────────────────
_PERIOD_DAYS: dict[str, int] = {
    "3M":  90,
    "1A":  365,
    "5A":  1825,
    "MAX": 0,   # 0 = limit=0 → tutta la storia disponibile
}

# ── Etichette pulsanti ────────────────────────────────────────────────────────
_TF_LABELS:     list[str] = ["1H", "4H", "1D", "1W"]
_PERIOD_LABELS: list[str] = ["3M", "1A", "5A", "MAX"]


def _compute_limit(tf_label: str, period_label: str) -> int:
    """
    Converte la coppia (timeframe, periodo) in numero di barre (limit).
    MAX → 0 (feed restituisce tutta la storia disponibile).
    """
    days = _PERIOD_DAYS[period_label]
    if days == 0:
        return 0  # MAX
    bars_per_day = _BARS_PER_DAY[tf_label]
    return max(1, round(bars_per_day * days))


# ── Stile QSS per i pulsanti segmented ───────────────────────────────────────
_BTN_BASE = (
    "QPushButton {"
    "  background: #21262d;"
    "  color: #a8b1bb;"
    "  border: 1px solid #30363d;"
    "  border-radius: 3px;"
    "  font-size: 11px;"
    "  font-weight: 600;"
    "  padding: 1px 8px;"
    "  min-height: 20px;"
    "  max-height: 20px;"
    "}"
    "QPushButton:hover {"
    "  background: #30363d;"
    "  color: #e6edf3;"
    "}"
    "QPushButton[active=true] {"
    "  background: #1f6feb;"
    "  color: #ffffff;"
    "  border-color: #388bfd;"
    "}"
)


class _SegmentedBar(QWidget):
    """
    Barra di pulsanti toggle (uno solo attivo per volta).
    Emette via callback on_changed(label: str).
    """

    def __init__(self, labels: list[str], default: str, parent=None):
        super().__init__(parent)
        self._active = default
        self._buttons: dict[str, QPushButton] = {}
        self._on_changed_cb = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)

        for lbl in labels:
            btn = QPushButton(lbl)
            btn.setStyleSheet(_BTN_BASE)
            btn.setCheckable(False)
            btn.setProperty("active", lbl == default)
            btn.clicked.connect(lambda checked, l=lbl: self._click(l))
            self._buttons[lbl] = btn
            row.addWidget(btn)

    def _click(self, label: str) -> None:
        if label == self._active:
            return
        self._active = label
        self._refresh_styles()
        if self._on_changed_cb:
            self._on_changed_cb(label)

    def _refresh_styles(self) -> None:
        for lbl, btn in self._buttons.items():
            btn.setProperty("active", lbl == self._active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def set_on_changed(self, cb) -> None:
        self._on_changed_cb = cb

    @property
    def active(self) -> str:
        return self._active


class ChartPanel(QWidget):
    """
    Main chart area con info bar + selettori TF/periodo + candlestick chart.

    Fetch autonomo: ascolta AppState.current_symbol_changed e ri-fetcha
    ad ogni cambio timeframe/periodo. Pattern asyncio identico a
    _FundamentalsStrip in dashboard.py.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._symbol = ""
        self._timeframe = ""
        self._df: Optional[pd.DataFrame] = None
        self._setup_ui()
        self._connect_state()
        self._boot_fetch()

    # ── Connessione AppState ──────────────────────────────────────────────────

    def _connect_state(self) -> None:
        """Ascolta AppState.current_symbol_changed per aggiornare info bar e fetch."""
        try:
            from gui.state.app_state import AppState
            state = AppState.instance()
            state.current_symbol_changed.connect(self._on_current_symbol_changed)
        except Exception:
            pass

    def _boot_fetch(self) -> None:
        """Fetch iniziale al boot con simbolo/TF/periodo correnti."""
        try:
            from gui.state.app_state import AppState
            symbol = AppState.instance().current_symbol
            if symbol:
                self._trigger_fetch(symbol)
        except Exception:
            pass

    def _on_current_symbol_changed(self, symbol_yf: str) -> None:
        """Cambio simbolo: aggiorna info bar e avvia fetch."""
        try:
            from core.engine import INSTRUMENTS
            display = INSTRUMENTS.get(symbol_yf, (symbol_yf,))[0]
        except Exception:
            display = symbol_yf
        self._lbl_symbol.setText(display)
        self._lbl_tf.setText("")
        self._lbl_price.setText("—")
        self._lbl_change.setText("")
        self._trigger_fetch(symbol_yf)

    def _trigger_fetch(self, symbol: str) -> None:
        """Avvia fetch OHLCV asincrono con TF e periodo correnti."""
        # Feedback immediato: mostra loading state prima che il coroutine parta
        self._set_loading_state(symbol)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._fetch_chart_data(symbol))
            # Se il loop non gira (test headless) il chart resta in empty state — OK.
            else:
                # In test headless: torna subito a idle (nessun fetch, ma neanche loading perpetuo)
                self._set_idle_state()
        except Exception:
            self._set_idle_state()

    async def _fetch_chart_data(self, symbol: str) -> None:
        """Scarica OHLCV e popola il chart. Mostra stato loading/error/idle."""
        tf_label = self._tf_bar.active
        period_label = self._period_bar.active
        tf_feed = _TF_MAP[tf_label]
        limit = _compute_limit(tf_label, period_label)
        try:
            from data.feed import UniversalDataFeed
            df = await UniversalDataFeed().get_ohlcv(symbol, tf_feed, limit=limit)
            if df is None or df.empty:
                # Simbolo non trovato (dati assenti o rete assente)
                self._set_error_state(symbol)
                return
            try:
                from core.engine import INSTRUMENTS
                display = INSTRUMENTS.get(symbol, (symbol,))[0]
            except Exception:
                display = symbol
            self.load_data(df, display, tf_feed)
            # load_data nasconde _empty e mostra il chart — StatusDot torna idle
            self._status_dot.set_state("idle")
        except Exception:
            self._set_error_state(symbol)

    # ── Loading state helpers ──────────────────────────────────────────────────

    def _set_loading_state(self, symbol: str) -> None:
        """Mostra il dot loading e aggiorna il testo dell'empty state."""
        self._status_dot.set_state("loading")
        self._empty_label.setText(tr("chart.loading_symbol", symbol=symbol))
        # Assicura che l'empty widget sia visibile (il chart potrebbe essere nascosto)
        self._chart.setVisible(False)
        self._empty.setVisible(True)

    def _set_idle_state(self) -> None:
        """Torna allo stato idle senza errori (usato in test headless)."""
        self._status_dot.set_state("idle")
        self._empty_label.setText(tr("chart.empty_state"))

    def _set_error_state(self, symbol: str) -> None:
        """Mostra il dot errore e aggiorna il testo dell'empty state."""
        self._status_dot.set_state("error")
        self._empty_label.setText(tr("chart.error_symbol", symbol=symbol))
        self._chart.setVisible(False)
        self._empty.setVisible(True)

    def _on_tf_changed(self, tf_label: str) -> None:
        """Cambio timeframe: ri-fetch."""
        self._do_refetch()

    def _on_period_changed(self, period_label: str) -> None:
        """Cambio periodo: ri-fetch."""
        self._do_refetch()

    def _do_refetch(self) -> None:
        """Recupera il simbolo corrente da AppState e avvia fetch."""
        try:
            from gui.state.app_state import AppState
            symbol = AppState.instance().current_symbol
            if symbol:
                self._trigger_fetch(symbol)
        except Exception:
            pass

    # ── Setup UI ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Info bar (56px) ───────────────────────────────────────────────
        info_bar = QWidget()
        info_bar.setStyleSheet("background:#161b22; border-bottom:1px solid #30363d;")
        info_bar.setFixedHeight(56)
        ib_layout = QHBoxLayout(info_bar)
        ib_layout.setContentsMargins(16, 0, 16, 0)
        ib_layout.setSpacing(16)

        # Symbol + timeframe badge
        self._lbl_symbol = QLabel("—")
        self._lbl_symbol.setStyleSheet(
            "font-size:18px; font-weight:700; color:#e6edf3; letter-spacing:0.5px;"
        )
        ib_layout.addWidget(self._lbl_symbol)

        self._lbl_tf = QLabel("")
        self._lbl_tf.setStyleSheet(
            "font-size:12px; color:#a8b1bb; background:#21262d; "
            "border-radius:4px; padding:2px 8px;"
        )
        ib_layout.addWidget(self._lbl_tf)

        ib_layout.addSpacing(8)

        # OHLCV info (aggiornata al hover dal chart)
        self._lbl_open  = self._make_ohlcv_label("O")
        self._lbl_high  = self._make_ohlcv_label("H")
        self._lbl_low   = self._make_ohlcv_label("L")
        self._lbl_close = self._make_ohlcv_label("C")
        self._lbl_vol   = self._make_ohlcv_label("V")
        for lbl in (self._lbl_open, self._lbl_high, self._lbl_low, self._lbl_close, self._lbl_vol):
            ib_layout.addWidget(lbl)

        ib_layout.addStretch()

        # Live price badge
        self._lbl_price = QLabel("—")
        self._lbl_price.setStyleSheet(
            "font-size:20px; font-weight:700; color:#e6edf3;"
        )
        ib_layout.addWidget(self._lbl_price)

        self._lbl_change = QLabel("")
        self._lbl_change.setStyleSheet("font-size:14px; color:#a8b1bb;")
        ib_layout.addWidget(self._lbl_change)

        layout.addWidget(info_bar)

        # ── Selector bar (28px) ───────────────────────────────────────────
        # Due gruppi di pulsanti: TF a sinistra, Periodo a destra.
        # Altezza fissa per coerenza con MA legend.
        selector_bar = QWidget()
        selector_bar.setStyleSheet(
            "background:#0d1117; border-bottom:1px solid #21262d;"
        )
        selector_bar.setFixedHeight(28)
        sel_layout = QHBoxLayout(selector_bar)
        sel_layout.setContentsMargins(12, 4, 12, 4)
        sel_layout.setSpacing(0)

        # Timeframe segmented
        self._tf_bar = _SegmentedBar(_TF_LABELS, default="1H")
        self._tf_bar.set_on_changed(self._on_tf_changed)
        sel_layout.addWidget(self._tf_bar)

        # Separatore verticale tra i due gruppi
        sep = QLabel("|")
        sep.setStyleSheet("color:#30363d; padding:0 10px; background:transparent;")
        sel_layout.addWidget(sep)

        # Periodo segmented
        self._period_bar = _SegmentedBar(_PERIOD_LABELS, default="1A")
        self._period_bar.set_on_changed(self._on_period_changed)
        sel_layout.addWidget(self._period_bar)

        sel_layout.addStretch()

        # StatusDot — feedback visivo loading/idle/error del fetch dati
        self._status_dot = StatusDot()
        self._status_dot.set_state("idle")
        sel_layout.addWidget(self._status_dot)

        layout.addWidget(selector_bar)

        # ── MA Legend (28px) ──────────────────────────────────────────────
        legend = QWidget()
        legend.setStyleSheet("background:#0d1117; border-bottom:1px solid #161b22;")
        legend.setFixedHeight(28)
        leg_layout = QHBoxLayout(legend)
        leg_layout.setContentsMargins(12, 0, 12, 0)
        leg_layout.setSpacing(16)

        for label, color in [("MA20", "#f0883e"), ("MA50", "#a371f7"), ("MA200", "#58a6ff")]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:10px;")
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{color}; font-size:11px; font-weight:600;")
            leg_layout.addWidget(dot)
            leg_layout.addWidget(lbl)

        leg_layout.addStretch()
        layout.addWidget(legend)

        # ── Chart ─────────────────────────────────────────────────────────
        self._chart = CandlestickChart()
        self._chart.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._chart.bar_hovered.connect(self._on_bar_hovered)
        layout.addWidget(self._chart)

        # ── Oscillator sub-chart (AI-selected, hidden by default) ─────────
        self._oscillator = OscillatorChart()
        self._oscillator.hide()
        layout.addWidget(self._oscillator)

        # ── Empty state ───────────────────────────────────────────────────
        self._empty = QWidget()
        self._empty.setStyleSheet("background:#0d1117;")
        em_layout = QVBoxLayout(self._empty)
        em_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label = QLabel(tr("chart.empty_state"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color:#6e7681; font-size:16px;")
        em_layout.addWidget(self._empty_label)
        layout.addWidget(self._empty)

        self._chart.setVisible(False)

    def _make_ohlcv_label(self, prefix: str) -> QLabel:
        lbl = QLabel(f"<span style='color:#6e7681'>{prefix}</span> —")
        lbl.setStyleSheet("font-size:12px; color:#a8b1bb;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl

    # ── Public API ────────────────────────────────────────────────────────────

    def load_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Mostra un nuovo dataset OHLCV nel chart."""
        if df is None or df.empty:
            return
        self._df = df
        self._symbol = symbol
        self._timeframe = timeframe

        self._lbl_symbol.setText(symbol)
        self._lbl_tf.setText(timeframe)

        # Mostra l'ultima barra nell'OHLCV info
        last = df.iloc[-1]
        self._update_ohlcv_labels(last)
        self._update_price_badge(last)

        self._chart.load_data(df, symbol, timeframe)
        self._empty.setVisible(False)
        self._chart.setVisible(True)

    def apply_ma_settings(self, ma20: bool, ma50: bool, ma200: bool):
        self._chart.set_ma_visible(ma20, ma50, ma200)

    def show_oscillator(self, column_name: str) -> None:
        """Mostra il sub-chart oscillatore selezionato dall'AI."""
        if self._df is None:
            return
        df = self._df
        if column_name not in df.columns:
            try:
                from indicators.technical import TechnicalIndicators
                df = TechnicalIndicators.compute_all(df)
                self._df = df
            except Exception:
                return

        if column_name not in df.columns:
            return

        if column_name == "macd_hist" and "macd" in df.columns and "macd_signal" in df.columns:
            self._oscillator.set_macd(
                df["macd"].reset_index(drop=True),
                df["macd_signal"].reset_index(drop=True),
                df["macd_hist"].reset_index(drop=True),
            )
        else:
            self._oscillator.set_oscillator(column_name, df[column_name].reset_index(drop=True))

        # Linka l'asse X dell'oscillatore al price plot per zoom/pan in sync
        self._oscillator.link_x_axis(self._chart._price_plot)
        self._oscillator.show()

    def update_live_tick(self, bar: dict, symbol: str):
        """Aggiorna l'ultima candela e l'info bar con un tick live."""
        if symbol != self._symbol:
            return
        price = bar.get("price")
        if price is None:
            return

        self._lbl_price.setText(f"{price:.3f}")
        self._chart.update_last_bar({
            "close": price,
            "high": bar.get("high", price),
            "low": bar.get("low", price),
            "volume": bar.get("volume", 0),
        })

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_bar_hovered(self, bar: dict):
        """Aggiorna OHLCV info bar dal crosshair hover del chart."""
        self._lbl_open.setText( f"<span style='color:#6e7681'>O</span> {bar['open']:.3f}")
        self._lbl_high.setText( f"<span style='color:#3fb950'>H</span> {bar['high']:.3f}")
        self._lbl_low.setText(  f"<span style='color:#f85149'>L</span> {bar['low']:.3f}")
        self._lbl_close.setText(f"<span style='color:#e6edf3'>C</span> {bar['close']:.3f}")
        self._lbl_vol.setText(  f"<span style='color:#6e7681'>V</span> {int(bar['volume']):,}")

    def _update_ohlcv_labels(self, row):
        self._lbl_open.setText( f"<span style='color:#6e7681'>O</span> {row['open']:.3f}")
        self._lbl_high.setText( f"<span style='color:#3fb950'>H</span> {row['high']:.3f}")
        self._lbl_low.setText(  f"<span style='color:#f85149'>L</span> {row['low']:.3f}")
        self._lbl_close.setText(f"<span style='color:#e6edf3'>C</span> {row['close']:.3f}")
        vol = row.get("volume", 0)
        self._lbl_vol.setText(  f"<span style='color:#6e7681'>V</span> {int(vol):,}")

    def _update_price_badge(self, last_row):
        price = last_row["close"]
        open_ = last_row["open"]
        self._lbl_price.setText(f"{price:.3f}")

        change = price - open_
        pct = (change / open_) * 100 if open_ else 0
        sign = "+" if change >= 0 else ""
        color = "#3fb950" if change >= 0 else "#f85149"
        self._lbl_change.setText(f"{sign}{change:.2f}  {sign}{pct:.2f}%")
        self._lbl_change.setStyleSheet(f"font-size:14px; color:{color};")
