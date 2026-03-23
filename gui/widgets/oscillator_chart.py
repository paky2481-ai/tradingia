"""
Oscillator Sub-Chart Widget

A pyqtgraph-based panel displayed below the volume chart showing
the AI-selected oscillator (RSI, MACD histogram, Stochastic, etc.)
"""

from typing import Optional

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout


_COLORS = {
    "rsi_14":    "#a371f7",   # purple
    "stoch_k":   "#58a6ff",   # blue
    "cci_20":    "#f0883e",   # orange
    "macd_hist": "#3fb950",   # green (positive) / #f85149 (negative)
    "mfi_14":    "#79c0ff",   # light blue
    "default":   "#8b949e",   # muted gray
}

_DISPLAY_NAMES = {
    "rsi_14":    "RSI (14)",
    "stoch_k":   "Stochastic %K",
    "cci_20":    "CCI (20)",
    "macd_hist": "MACD Histogram",
    "mfi_14":    "MFI (14)",
}

_LEVELS = {
    "rsi_14":    (70.0, 30.0, 50.0),   # (overbought, oversold, mid)
    "stoch_k":   (80.0, 20.0, 50.0),
    "cci_20":    (100.0, -100.0, 0.0),
    "mfi_14":    (80.0, 20.0, 50.0),
    "macd_hist": (None, None, 0.0),
}


class OscillatorChart(QWidget):
    """
    Pyqtgraph oscillator panel.
    Supports: RSI, Stochastic %K, CCI, MACD histogram, MFI.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._name: str = ""
        self._setup_ui()

    # ── Setup ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Label bar
        self._header = QLabel("Oscillator")
        self._header.setStyleSheet(
            "background:#161b22; color:#8b949e; font-size:11px;"
            " padding:2px 8px; border-top:1px solid #30363d;"
        )
        layout.addWidget(self._header)

        # pyqtgraph plot
        self._gw = pg.GraphicsLayoutWidget()
        self._gw.setBackground("#0d1117")
        self._gw.setMinimumHeight(80)
        self._gw.setMaximumHeight(120)
        layout.addWidget(self._gw)

        self._plot = self._gw.addPlot()
        self._plot.setMenuEnabled(False)
        self._plot.showGrid(x=False, y=True, alpha=0.15)
        self._plot.setDefaultPadding(0.02)

        # Style axes
        for ax in ("left", "bottom", "top", "right"):
            axis = self._plot.getAxis(ax)
            axis.setPen(pg.mkPen(color="#30363d"))
            axis.setTextPen(pg.mkPen(color="#8b949e"))
        self._plot.getAxis("bottom").hide()
        self._plot.getAxis("right").show()
        self._plot.getAxis("left").setWidth(0)
        self._plot.getAxis("right").setWidth(44)

        # Line items (lazy-created)
        self._line: Optional[pg.PlotDataItem] = None
        self._bar_items: list = []
        self._ob_line: Optional[pg.InfiniteLine] = None
        self._os_line: Optional[pg.InfiniteLine] = None
        self._mid_line: Optional[pg.InfiniteLine] = None

    # ── Public API ────────────────────────────────────────────────────────

    def set_oscillator(
        self,
        name: str,
        values: pd.Series,
    ) -> None:
        """Display a standard oscillator (RSI, Stochastic, CCI, MFI)."""
        self._name = name
        self._plot.clear()
        self._bar_items.clear()

        display = _DISPLAY_NAMES.get(name, name.upper())
        self._header.setText(f"  {display}")

        vals = values.dropna().values.astype(float)
        if len(vals) == 0:
            return

        x = np.arange(len(vals))
        color = _COLORS.get(name, _COLORS["default"])
        levels = _LEVELS.get(name, (None, None, 0.0))
        ob, os_, mid = levels

        # Main line
        self._plot.plot(
            x, vals,
            pen=pg.mkPen(color=color, width=1.2),
        )

        # Reference levels
        if ob is not None:
            self._plot.addItem(
                pg.InfiniteLine(
                    pos=ob, angle=0,
                    pen=pg.mkPen(color="#f85149", width=0.7, style=Qt.PenStyle.DashLine),
                )
            )
        if os_ is not None:
            self._plot.addItem(
                pg.InfiniteLine(
                    pos=os_, angle=0,
                    pen=pg.mkPen(color="#3fb950", width=0.7, style=Qt.PenStyle.DashLine),
                )
            )
        if mid is not None:
            self._plot.addItem(
                pg.InfiniteLine(
                    pos=mid, angle=0,
                    pen=pg.mkPen(color="#30363d", width=0.7),
                )
            )

        # Y-range with padding
        y_min = float(np.nanmin(vals))
        y_max = float(np.nanmax(vals))
        pad = (y_max - y_min) * 0.1 or 5.0
        self._plot.setYRange(y_min - pad, y_max + pad, padding=0)

    def set_macd(
        self,
        macd: pd.Series,
        signal: pd.Series,
        hist: pd.Series,
    ) -> None:
        """Display MACD with signal line and histogram."""
        self._name = "macd_hist"
        self._plot.clear()
        self._bar_items.clear()
        self._header.setText("  MACD")

        hist_vals = hist.values.astype(float)
        macd_vals = macd.values.astype(float)
        sig_vals = signal.values.astype(float)
        n = len(hist_vals)

        if n == 0:
            return

        x = np.arange(n)

        # Histogram bars (green positive, red negative)
        for i in range(n):
            v = hist_vals[i]
            if np.isnan(v):
                continue
            color = "#3fb950" if v >= 0 else "#f85149"
            bar = pg.BarGraphItem(
                x=[i], height=[abs(v)],
                y0=min(0, v),
                width=0.6,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(None),
            )
            self._plot.addItem(bar)

        # MACD and signal lines
        mask = ~np.isnan(macd_vals)
        if mask.any():
            self._plot.plot(x[mask], macd_vals[mask],
                            pen=pg.mkPen(color="#58a6ff", width=1.0))
        mask2 = ~np.isnan(sig_vals)
        if mask2.any():
            self._plot.plot(x[mask2], sig_vals[mask2],
                            pen=pg.mkPen(color="#f0883e", width=1.0))

        # Zero line
        self._plot.addItem(
            pg.InfiniteLine(pos=0, angle=0,
                            pen=pg.mkPen(color="#30363d", width=0.8))
        )

        y_min = float(np.nanmin(np.concatenate([hist_vals, macd_vals])))
        y_max = float(np.nanmax(np.concatenate([hist_vals, macd_vals])))
        pad = (y_max - y_min) * 0.15 or 0.01
        self._plot.setYRange(y_min - pad, y_max + pad, padding=0)

    def link_x_axis(self, other_plot: pg.PlotItem) -> None:
        """Link X-axis to another plot for synchronised zoom/pan."""
        self._plot.setXLink(other_plot)

    def clear(self) -> None:
        self._plot.clear()
        self._bar_items.clear()
        self._header.setText("  Oscillator")
