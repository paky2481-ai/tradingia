"""
Chart Panel
Hosts the CandlestickChart and a top info bar with symbol/price/change info.
"""

from __future__ import annotations

from typing import Optional
import pandas as pd

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy,
)

from gui.widgets.candlestick_chart import CandlestickChart
from gui.widgets.oscillator_chart import OscillatorChart


class ChartPanel(QWidget):
    """Main chart area with info bar + candlestick chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._symbol = ""
        self._timeframe = ""
        self._df: Optional[pd.DataFrame] = None
        self._setup_ui()

    # ── Setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Info bar ───────────────────────────────────────────────────
        info_bar = QWidget()
        info_bar.setStyleSheet("background:#161b22; border-bottom:1px solid #30363d;")
        info_bar.setFixedHeight(56)
        ib_layout = QHBoxLayout(info_bar)
        ib_layout.setContentsMargins(16, 0, 16, 0)
        ib_layout.setSpacing(16)

        # Symbol + timeframe
        self._lbl_symbol = QLabel("—")
        self._lbl_symbol.setStyleSheet(
            "font-size:18px; font-weight:700; color:#e6edf3; letter-spacing:0.5px;"
        )
        ib_layout.addWidget(self._lbl_symbol)

        self._lbl_tf = QLabel("")
        self._lbl_tf.setStyleSheet(
            "font-size:12px; color:#8b949e; background:#21262d; "
            "border-radius:4px; padding:2px 8px;"
        )
        ib_layout.addWidget(self._lbl_tf)

        ib_layout.addSpacing(8)

        # OHLCV info (updated on hover by chart)
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
        self._lbl_change.setStyleSheet("font-size:14px; color:#8b949e;")
        ib_layout.addWidget(self._lbl_change)

        layout.addWidget(info_bar)

        # ── MA Legend ─────────────────────────────────────────────────
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

        # ── Chart ──────────────────────────────────────────────────────
        self._chart = CandlestickChart()
        self._chart.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._chart.bar_hovered.connect(self._on_bar_hovered)
        layout.addWidget(self._chart)

        # ── Oscillator sub-chart (AI-selected, hidden by default) ──────
        self._oscillator = OscillatorChart()
        self._oscillator.hide()
        layout.addWidget(self._oscillator)

        # ── Empty state ────────────────────────────────────────────────
        self._empty = QWidget()
        self._empty.setStyleSheet("background:#0d1117;")
        em_layout = QVBoxLayout(self._empty)
        em_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_lbl = QLabel("Select a symbol and click\n\"Load Historical Data\"")
        em_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_lbl.setStyleSheet("color:#484f58; font-size:16px;")
        em_layout.addWidget(em_lbl)
        layout.addWidget(self._empty)

        self._chart.setVisible(False)

    def _make_ohlcv_label(self, prefix: str) -> QLabel:
        lbl = QLabel(f"<span style='color:#484f58'>{prefix}</span> —")
        lbl.setStyleSheet("font-size:12px; color:#8b949e;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        return lbl

    # ── Public API ────────────────────────────────────────────────────────

    def load_data(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """Display a new OHLCV dataset."""
        if df is None or df.empty:
            return
        self._df = df
        self._symbol = symbol
        self._timeframe = timeframe

        self._lbl_symbol.setText(symbol)
        self._lbl_tf.setText(timeframe)

        # Show last bar OHLCV
        last = df.iloc[-1]
        self._update_ohlcv_labels(last)
        self._update_price_badge(last)

        self._chart.load_data(df, symbol, timeframe)
        self._empty.setVisible(False)
        self._chart.setVisible(True)

    def apply_ma_settings(self, ma20: bool, ma50: bool, ma200: bool):
        self._chart.set_ma_visible(ma20, ma50, ma200)

    def show_oscillator(self, column_name: str) -> None:
        """Display the AI-selected oscillator sub-chart."""
        if self._df is None:
            return
        # Compute indicator if not in df
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
            self._oscillator.set_macd(df["macd"], df["macd_signal"], df["macd_hist"])
        else:
            self._oscillator.set_oscillator(column_name, df[column_name])

        # Link oscillator X-axis to main price plot so zoom/pan stays in sync
        self._oscillator.link_x_axis(self._chart._price_plot)
        self._oscillator.show()

    def update_live_tick(self, bar: dict, symbol: str):
        """Update the last candle and info bar with a live tick."""
        if symbol != self._symbol:
            return
        price = bar.get("price")
        if price is None:
            return

        # Update price badge
        self._lbl_price.setText(f"{price:.4f}")

        # Update chart last bar
        self._chart.update_last_bar({
            "close": price,
            "high": bar.get("high", price),
            "low": bar.get("low", price),
            "volume": bar.get("volume", 0),
        })

    # ── Internals ─────────────────────────────────────────────────────────

    def _on_bar_hovered(self, bar: dict):
        """Update OHLCV info bar from chart crosshair hover."""
        self._lbl_open.setText( f"<span style='color:#484f58'>O</span> {bar['open']:.4f}")
        self._lbl_high.setText( f"<span style='color:#3fb950'>H</span> {bar['high']:.4f}")
        self._lbl_low.setText(  f"<span style='color:#f85149'>L</span> {bar['low']:.4f}")
        self._lbl_close.setText(f"<span style='color:#e6edf3'>C</span> {bar['close']:.4f}")
        self._lbl_vol.setText(  f"<span style='color:#484f58'>V</span> {int(bar['volume']):,}")

    def _update_ohlcv_labels(self, row):
        o = row.get("open", row["open"] if "open" in row.index else None)
        self._lbl_open.setText( f"<span style='color:#484f58'>O</span> {row['open']:.4f}")
        self._lbl_high.setText( f"<span style='color:#3fb950'>H</span> {row['high']:.4f}")
        self._lbl_low.setText(  f"<span style='color:#f85149'>L</span> {row['low']:.4f}")
        self._lbl_close.setText(f"<span style='color:#e6edf3'>C</span> {row['close']:.4f}")
        vol = row.get("volume", 0)
        self._lbl_vol.setText(  f"<span style='color:#484f58'>V</span> {int(vol):,}")

    def _update_price_badge(self, last_row):
        price = last_row["close"]
        open_ = last_row["open"]
        self._lbl_price.setText(f"{price:.4f}")

        change = price - open_
        pct = (change / open_) * 100 if open_ else 0
        sign = "+" if change >= 0 else ""
        color = "#3fb950" if change >= 0 else "#f85149"
        self._lbl_change.setText(f"{sign}{change:.2f}  {sign}{pct:.2f}%")
        self._lbl_change.setStyleSheet(f"font-size:14px; color:{color};")
