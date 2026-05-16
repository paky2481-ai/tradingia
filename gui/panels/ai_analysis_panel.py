"""
AI Analysis Panel

Shows the full AI analysis for the currently loaded symbol:
  - Market regime + Hurst exponent
  - Dominant cycle period
  - Fundamental score
  - Selected indicators with weights
  - Final AI signal with confidence breakdown
  - Active strategy + tuned parameters
  - "Run AI Analysis" button

Fase 5.2: ascolta bus.qt.ai_result, regime_update, kelly_update.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from gui.i18n import tr

import pandas as pd
from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QProgressBar,
    QGridLayout, QCheckBox,
)

from gui.widgets.info import (
    RegimePill, Gauge, ConfidenceBar, BiDirectionalBar, FFTMini, Sparkline,
)

_UI = Path(__file__).parent.parent / "ui" / "ai_analysis_panel.ui"


# ── Reusable small widgets ────────────────────────────────────────────────────

class _BarWidget(QWidget):
    """Horizontal fill bar from -1 to +1 (or 0 to 1)."""

    def __init__(self, value: float = 0.0, symmetric: bool = True, parent=None):
        super().__init__(parent)
        self._value = value
        self._symmetric = symmetric
        self.setFixedHeight(10)
        self.setMinimumWidth(80)

    def set_value(self, v: float):
        self._value = max(-1.0, min(1.0, v))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        # Background
        painter.fillRect(0, 0, w, h, QColor("#21262d"))

        v = self._value
        if self._symmetric:
            mid = w // 2
            bar_w = int(abs(v) * mid)
            color = QColor("#3fb950") if v >= 0 else QColor("#f85149")
            if v >= 0:
                painter.fillRect(mid, 1, bar_w, h - 2, color)
            else:
                painter.fillRect(mid - bar_w, 1, bar_w, h - 2, color)
        else:
            bar_w = int(v * w)
            color = QColor("#58a6ff")
            painter.fillRect(0, 1, bar_w, h - 2, color)

        painter.end()


class _Section(QFrame):
    """Labelled section with thin top border."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { border:none; background:transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 2)
        layout.setSpacing(4)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            "color:#58a6ff; font-size:10px; font-weight:bold; "
            "border-bottom:1px solid #21262d; padding-bottom:2px;"
        )
        layout.addWidget(lbl)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(2)
        layout.addWidget(self._content)

    def content(self) -> QVBoxLayout:
        return self._content_layout

    def clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


def _row(label: str, value: str, value_color: str = "#e6edf3") -> QWidget:
    w = QWidget()
    hl = QHBoxLayout(w)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet("color:#a8b1bb; font-size:11px;")
    val = QLabel(value)
    val.setStyleSheet(f"color:{value_color}; font-size:11px; font-weight:bold;")
    val.setAlignment(Qt.AlignmentFlag.AlignRight)
    hl.addWidget(lbl, 1)
    hl.addWidget(val, 0)
    return w


# ── Main Panel ────────────────────────────────────────────────────────────────

class AIAnalysisPanel(QWidget):
    """
    Right-side dock panel showing the full AI analysis result.

    Signals:
        analysis_complete(dict)  – emitted when analysis finishes
        oscillator_changed(str)  – emitted when AI selects a different oscillator

    Fase 5.2: listener bus.qt.ai_result, regime_update, kelly_update.
    """

    analysis_complete = pyqtSignal(object)    # AutoConfigResult
    oscillator_changed = pyqtSignal(str)      # oscillator column name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._symbol: str = ""
        self._df: Optional[pd.DataFrame] = None
        self._asset_type: str = "stock"
        self._auto_enabled: bool = True
        self._running: bool = False

        # Fase 5.2 — storico predizioni per sparkline
        self._prediction_history: list[float] = []

        uic.loadUi(str(_UI), self)
        self._apply_styles()
        self._build_dynamic_content()
        self._connect_signals()
        self._connect_bus()

    # ── UI Setup ──────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet("background:#0d1117; color:#e6edf3;")
        self._header.setStyleSheet("background:#161b22; border-bottom:1px solid #30363d;")
        self._lbl_title.setStyleSheet("color:#e6edf3; font-weight:bold; font-size:12px;")
        self._chk_auto.setStyleSheet("color:#a8b1bb; font-size:10px;")
        self._btn_run.setStyleSheet(
            "QPushButton { background:#238636; color:#fff; border:none; "
            "padding:6px; font-size:11px; }"
            "QPushButton:hover { background:#2ea043; }"
            "QPushButton:disabled { background:#161b22; color:#6e7681; }"
        )
        self._progress.setStyleSheet(
            "QProgressBar { background:#161b22; border:none; }"
            "QProgressBar::chunk { background:#388bfd; }"
        )
        self._scroll_area.setStyleSheet(
            "QScrollArea { border:none; background:#0d1117; }"
            "QScrollBar:vertical { background:#161b22; width:6px; }"
            "QScrollBar::handle:vertical { background:#30363d; border-radius:3px; }"
        )
        self._scroll_content.setStyleSheet("background:#0d1117;")

    def _build_dynamic_content(self):
        """Aggiunge sezioni dinamiche e label vuota al layout dello scroll content."""
        self._content_layout = self._scroll_content.layout()

        # ── Fase 5.2: header con RegimePill + ConfidenceBar + BiDirectionalBar ──
        self._header_sec = _Section("Regime & Signal")
        hc = self._header_sec.content()

        # RegimePill in riga con label
        pill_row = QWidget()
        pill_hl = QHBoxLayout(pill_row)
        pill_hl.setContentsMargins(0, 0, 0, 0)
        pill_hl.setSpacing(6)
        pill_lbl = QLabel("Regime:")
        pill_lbl.setStyleSheet("color:#a8b1bb; font-size:11px;")
        pill_hl.addWidget(pill_lbl)
        self._regime_pill = RegimePill()
        pill_hl.addWidget(self._regime_pill)
        pill_hl.addStretch()
        hc.addWidget(pill_row)

        # ConfidenceBar
        self._confidence_bar = ConfidenceBar()
        self._confidence_bar.set_label("CONFIDENCE")
        self._confidence_bar.set_threshold(0.7)
        hc.addWidget(self._confidence_bar)

        # BiDirectionalBar (prediction direction)
        self._bidir_bar = BiDirectionalBar()
        hc.addWidget(self._bidir_bar)

        # ── Gauge Hurst ───────────────────────────────────────────────────────
        self._gauge_hurst = Gauge(label=tr("gauge.hurst"))
        hc.addWidget(self._gauge_hurst)

        # ── Gauge Kelly ───────────────────────────────────────────────────────
        self._gauge_kelly = Gauge(
            label=tr("gauge.kelly"),
            zones=[(0.0, 0.05, "#3fb950"), (0.05, 0.15, "#d29922"), (0.15, 1.0, "#f85149")],
        )
        hc.addWidget(self._gauge_kelly)

        self._content_layout.addWidget(self._header_sec)

        # ── FFTMini ───────────────────────────────────────────────────────────
        self._fft_sec = _Section("Cycle Spectrum (FFT)")
        self._fft_mini = FFTMini()
        self._fft_mini.set_spectrum([0.1] * 10)  # placeholder finché non arriva CycleAnalysis
        self._fft_sec.content().addWidget(self._fft_mini)
        self._content_layout.addWidget(self._fft_sec)

        # ── Sparkline storia predizioni ───────────────────────────────────────
        self._spark_sec = _Section("History (50 pred.)")
        spark_row = QWidget()
        spark_hl = QHBoxLayout(spark_row)
        spark_hl.setContentsMargins(0, 0, 0, 0)
        spark_hl.setSpacing(4)
        self._pred_sparkline = Sparkline(width=120, height=28, marker_mode="hit_miss")
        spark_hl.addWidget(self._pred_sparkline)
        spark_hl.addStretch()
        self._spark_sec.content().addWidget(spark_row)
        self._content_layout.addWidget(self._spark_sec)

        # ── Sezioni analisi tradizionali ─────────────────────────────────────
        self._sec_regime      = _Section("Regime & Cycles")
        self._sec_fundamental = _Section("Fundamental Score")
        self._sec_indicators  = _Section("AI-Selected Indicators")
        self._sec_strategy    = _Section("Active Strategy")
        self._sec_signal      = _Section("AI Signal")

        for sec in [
            self._sec_regime, self._sec_fundamental,
            self._sec_indicators, self._sec_strategy, self._sec_signal,
        ]:
            self._content_layout.addWidget(sec)

        self._content_layout.addStretch(1)

        self._lbl_empty = QLabel(tr("ai.empty_state"))
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setStyleSheet("color:#6e7681; font-size:11px; padding:16px;")
        self._content_layout.insertWidget(0, self._lbl_empty)

        self._hide_sections()

    def _connect_signals(self):
        self._chk_auto.toggled.connect(self._on_auto_toggled)
        self._btn_run.clicked.connect(self._on_run_clicked)

    def _connect_bus(self):
        """Fase 5.2 — collega segnali SignalBus in lazy mode."""
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.qt.ai_result.connect(self._on_ai_result)
            bus.qt.regime_update.connect(self._on_regime_update)
            bus.qt.kelly_update.connect(self._on_kelly_update)
        except Exception:
            pass  # bus non disponibile in test headless

    # ── Public API ────────────────────────────────────────────────────────

    def set_symbol(self, symbol: str, df: pd.DataFrame, asset_type: str = "stock"):
        """Called by MainWindow when a new symbol is loaded."""
        self._symbol = symbol
        self._df = df
        self._asset_type = asset_type
        self._btn_run.setText(tr("ai.btn_run", symbol=symbol))
        self._btn_run.setEnabled(True)

        if self._auto_enabled:
            # Schedule auto-run after a short delay
            QTimer.singleShot(500, self._on_run_clicked)

    def update_from_result(self, result) -> None:
        """Populate all sections from an AutoConfigResult."""
        if result is None:
            return

        self._lbl_empty.hide()
        self._show_sections()

        self._fill_regime(result)
        self._fill_fundamental(result)
        self._fill_indicators(result)
        self._fill_strategy(result)
        self._fill_signal(result)

        self.analysis_complete.emit(result)
        if result.oscillator_for_chart:
            self.oscillator_changed.emit(result.oscillator_for_chart)

    # ── Button handlers ───────────────────────────────────────────────────

    def _on_run_clicked(self):
        if self._running or self._df is None or not self._symbol:
            return
        self._running = True
        self._btn_run.setEnabled(False)
        self._progress.show()
        asyncio.ensure_future(self._run_analysis())

    def _on_auto_toggled(self, checked: bool):
        self._auto_enabled = checked

    # ── Fase 5.2 — Bus slots ──────────────────────────────────────────────

    @pyqtSlot(object)
    def _on_ai_result(self, event):
        """Aggiorna widget da AIResultEvent emesso dal bus."""
        try:
            # Gauge Hurst
            self._gauge_hurst.set_value(event.hurst)
            # ConfidenceBar
            self._confidence_bar.set_value(event.confidence)
            # BiDirectionalBar: derivo bull/bear da price_direction
            pd_val = float(event.price_direction)
            if pd_val > 0:
                bull = min(1.0, 0.5 + abs(pd_val))
                bear = max(0.0, 0.5 - abs(pd_val))
            else:
                bear = min(1.0, 0.5 + abs(pd_val))
                bull = max(0.0, 0.5 - abs(pd_val))
            self._bidir_bar.set_split(bull, bear)
            # Aggiorna storico sparkline: 1.0 = hit (long+positive / short+negative), 0.0 = miss
            hit = 1.0 if (event.prediction in ("long", "neutral") and pd_val >= 0) \
                      or (event.prediction == "short" and pd_val < 0) else 0.0
            self._prediction_history.append(hit)
            if len(self._prediction_history) > 50:
                self._prediction_history = self._prediction_history[-50:]
            self._pred_sparkline.set_values(self._prediction_history)
            # Aggiorna anche RegimePill
            self._regime_pill.set_regime(event.regime, event.hurst)
        except Exception:
            pass

    @pyqtSlot(str, float)
    def _on_regime_update(self, regime: str, hurst: float):
        """Aggiorna solo RegimePill + Gauge Hurst."""
        try:
            self._regime_pill.set_regime(regime, hurst)
            self._gauge_hurst.set_value(hurst)
        except Exception:
            pass

    @pyqtSlot(float)
    def _on_kelly_update(self, kelly_pct: float):
        """Aggiorna Gauge Kelly."""
        try:
            self._gauge_kelly.set_value(kelly_pct)
        except Exception:
            pass

    # ── Async analysis ────────────────────────────────────────────────────

    async def _run_analysis(self):
        try:
            from strategies.strategy_manager import StrategyManager
            manager = StrategyManager()
            result = await manager.run_analysis(
                self._symbol, self._df, self._asset_type
            )
            self.update_from_result(result)
        except Exception as e:
            self._lbl_empty.setText(tr("ai.analysis_error", error=e))
            self._lbl_empty.show()
        finally:
            self._running = False
            self._btn_run.setEnabled(True)
            self._progress.hide()

    # ── Section fillers ───────────────────────────────────────────────────

    def _fill_regime(self, r):
        sec = self._sec_regime
        sec.clear_content()
        c = sec.content()

        regime_color = {
            "trending": "#3fb950",
            "cycling":  "#f0883e",
            "choppy":   "#a8b1bb",
        }.get(r.regime, "#a8b1bb")

        c.addWidget(_row("Regime", r.regime.capitalize(), regime_color))

        hurst = r.hurst
        hurst_color = "#3fb950" if hurst > 0.55 else ("#f0883e" if hurst < 0.45 else "#a8b1bb")
        hurst_row = QWidget()
        hl = QHBoxLayout(hurst_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        lbl_hurst = QLabel("Hurst")
        lbl_hurst.setStyleSheet("color:#a8b1bb; font-size:11px;")
        hl.addWidget(lbl_hurst)
        bar = _BarWidget(value=hurst * 2 - 1, symmetric=False)  # map 0-1 → 0-1 bar
        bar.set_value(hurst)
        hl.addWidget(bar, 1)
        val_lbl = QLabel(f"{hurst:.3f}")
        val_lbl.setStyleSheet(f"color:{hurst_color}; font-size:11px; font-weight:bold;")
        hl.addWidget(val_lbl)
        c.addWidget(hurst_row)

        c.addWidget(_row("Dominant Cycle", f"{r.dominant_period} bars"))
        c.addWidget(_row("ADX", "—"))

    def _fill_fundamental(self, r):
        sec = self._sec_fundamental
        sec.clear_content()
        c = sec.content()

        score = r.fundamental_score
        score_color = "#3fb950" if score > 0.2 else ("#f85149" if score < -0.2 else "#a8b1bb")

        row_w = QWidget()
        hl = QHBoxLayout(row_w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        lbl = QLabel("Score")
        lbl.setStyleSheet("color:#a8b1bb; font-size:11px;")
        hl.addWidget(lbl)
        bar = _BarWidget(score, symmetric=True)
        hl.addWidget(bar, 1)
        val_lbl = QLabel(f"{score:+.2f}")
        val_lbl.setStyleSheet(f"color:{score_color}; font-size:11px; font-weight:bold;")
        hl.addWidget(val_lbl)
        c.addWidget(row_w)

    def _fill_indicators(self, r):
        sec = self._sec_indicators
        sec.clear_content()
        c = sec.content()

        weights = r.indicator_weights
        if not weights:
            c.addWidget(_row("No data", "—"))
            return

        max_w = max(weights.values()) if weights else 1.0
        for ind_name in r.active_indicators:
            w = weights.get(ind_name, 0.0)
            row_w = QWidget()
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)
            lbl = QLabel(ind_name)
            lbl.setStyleSheet("color:#a8b1bb; font-size:10px;")
            hl.addWidget(lbl, 2)
            bar = _BarWidget(w / max_w if max_w > 0 else 0, symmetric=False)
            hl.addWidget(bar, 3)
            pct_lbl = QLabel(f"{w:.3f}")
            pct_lbl.setStyleSheet("color:#6e7681; font-size:10px;")
            hl.addWidget(pct_lbl)
            c.addWidget(row_w)

    def _fill_strategy(self, r):
        sec = self._sec_strategy
        sec.clear_content()
        c = sec.content()

        strat_labels = {
            "ai_ensemble":     ("AI Ensemble",        "#a371f7"),
            "trend_following": ("Trend Following",     "#58a6ff"),
            "mean_reversion":  ("Mean Reversion",      "#f0883e"),
            "breakout":        ("Breakout",            "#3fb950"),
            "scalping":        ("Scalping",            "#ffa657"),
        }
        label, color = strat_labels.get(r.recommended_strategy, (r.recommended_strategy, "#a8b1bb"))
        c.addWidget(_row("Strategy", label, color))

        if r.tuned_params:
            for k, v in r.tuned_params.items():
                c.addWidget(_row(f"  {k}", str(v)))

    def _fill_signal(self, r):
        sec = self._sec_signal
        sec.clear_content()
        c = sec.content()

        confidence = r.confidence
        conf_color = "#3fb950" if confidence > 0.65 else ("#f0883e" if confidence > 0.45 else "#f85149")

        regime_to_bias = {
            "trending": ("BUY" if r.hurst > 0.5 else "SELL", confidence),
            "cycling":  ("NEUTRAL", confidence * 0.7),
            "choppy":   ("NEUTRAL", confidence * 0.5),
        }
        direction, conf = regime_to_bias.get(r.regime, ("NEUTRAL", 0.5))
        dir_color = "#3fb950" if direction == "BUY" else ("#f85149" if direction == "SELL" else "#a8b1bb")

        c.addWidget(_row("Direction", direction, dir_color))

        conf_row = QWidget()
        hl = QHBoxLayout(conf_row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        lbl = QLabel("Confidence")
        lbl.setStyleSheet("color:#a8b1bb; font-size:11px;")
        hl.addWidget(lbl)
        bar = _BarWidget(conf, symmetric=False)
        hl.addWidget(bar, 1)
        pct = QLabel(f"{conf * 100:.0f}%")
        pct.setStyleSheet(f"color:{conf_color}; font-size:11px; font-weight:bold;")
        hl.addWidget(pct)
        c.addWidget(conf_row)

        hurst_bias = (
            tr("ai.hurst_bias.trending") if r.hurst > 0.55 else
            (tr("ai.hurst_bias.reverting") if r.hurst < 0.45 else tr("ai.hurst_bias.random"))
        )
        c.addWidget(_row("Hurst bias", hurst_bias))
        fund_support = (
            tr("ai.fund_support.yes") if r.fundamental_score > 0.15 else
            (tr("ai.fund_support.negative") if r.fundamental_score < -0.15 else tr("ai.fund_support.neutral"))
        )
        c.addWidget(_row("Fund. support",
                         fund_support,
                         "#3fb950" if r.fundamental_score > 0.15 else ("#f85149" if r.fundamental_score < -0.15 else "#a8b1bb")))

    # ── Visibility helpers ─────────────────────────────────────────────────

    def _hide_sections(self):
        for sec in [
            self._sec_regime, self._sec_fundamental,
            self._sec_indicators, self._sec_strategy, self._sec_signal,
        ]:
            sec.hide()

    def _show_sections(self):
        for sec in [
            self._sec_regime, self._sec_fundamental,
            self._sec_indicators, self._sec_strategy, self._sec_signal,
        ]:
            sec.show()
