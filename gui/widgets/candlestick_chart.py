"""
Candlestick Chart Widget
High-performance real-time chart using pyqtgraph.
Supports: OHLCV candlesticks, volume bars, indicator overlays.
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QPicture, QPen, QBrush, QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

# ── Colors ────────────────────────────────────────────────────────────────
C_BG        = "#0d1117"
C_BG2       = "#161b22"
C_GRID      = "#21262d"
C_TEXT      = "#8b949e"
C_BULL      = "#3fb950"   # green candle
C_BEAR      = "#f85149"   # red candle
C_BULL_BODY = "#2ea04388"
C_BEAR_BODY = "#da363388"
C_VOLUME    = "#1f6feb66"
C_VOLUME_UP = "#3fb95044"
C_VOLUME_DN = "#f8514944"
C_CURSOR    = "#388bfd"
C_MA20      = "#f0883e"
C_MA50      = "#a371f7"
C_MA200     = "#58a6ff"


def _hex(color: str) -> QColor:
    return QColor(color)


class CandlestickItem(pg.GraphicsObject):
    """Custom pyqtgraph item to draw OHLCV candlesticks."""

    def __init__(self):
        super().__init__()
        self._picture: Optional[QPicture] = None
        self._data: Optional[pd.DataFrame] = None
        self._bounds = QRectF()

    def set_data(self, df: pd.DataFrame):
        """df must have columns: open, high, low, close, volume; numeric index 0..n-1."""
        self._data = df.reset_index(drop=True)
        self._picture = None
        self._render()
        self.informViewBoundsChanged()
        self.update()

    def dataBounds(self, ax, frac=1.0, orthoRange=None):
        """Called by pyqtgraph setAutoVisible() to get visible data range."""
        if self._data is None or self._data.empty:
            return None, None
        df = self._data
        if ax == 0:
            return 0, len(df) - 1
        if orthoRange is not None:
            x0, x1 = int(max(0, orthoRange[0])), int(min(len(df) - 1, orthoRange[1]))
            visible = df.iloc[x0:x1 + 1]
            if visible.empty:
                return None, None
        else:
            visible = df
        return float(visible["low"].min()), float(visible["high"].max())

    def _render(self):
        if self._data is None or self._data.empty:
            return

        picture = QPicture()
        painter = QPainter(picture)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        df = self._data
        n = len(df)
        w = 0.3  # half-candle width

        min_price = df["low"].min()
        max_price = df["high"].max()
        self._bounds = QRectF(0, min_price, n, max_price - min_price)

        # width=0 → cosmetic pen: sempre 1px fisico, indipendente dallo zoom/scala.
        # Se si usa width=1 in coordinate dati, per forex (scala ~10000 px/unit)
        # il pen diventa 10000px e le barre coprono tutto il grafico.
        pen_bull = QPen(_hex(C_BULL), 0)
        pen_bear = QPen(_hex(C_BEAR), 0)
        brush_bull = QBrush(_hex(C_BULL))
        brush_bear = QBrush(_hex(C_BEAR))
        brush_doji = QBrush(Qt.BrushStyle.NoBrush)

        for i in range(n):
            row = df.iloc[i]
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            is_bull = c >= o

            pen = pen_bull if is_bull else pen_bear
            painter.setPen(pen)

            # Wick
            painter.drawLine(
                pg.Point(i, l),
                pg.Point(i, h),
            )

            # Body
            body_top = max(o, c)
            body_bot = min(o, c)
            body_h = body_top - body_bot

            if body_h < 1e-10:  # doji
                painter.setBrush(brush_doji)
                body_h = (max_price - min_price) * 0.002
            else:
                painter.setBrush(brush_bull if is_bull else brush_bear)

            painter.drawRect(QRectF(i - w, body_bot, 2 * w, body_h))

        painter.end()
        self._picture = picture

    def paint(self, painter: QPainter, *args):
        if self._picture:
            painter.drawPicture(0, 0, self._picture)

    def boundingRect(self) -> QRectF:
        return self._bounds


class VolumeItem(pg.GraphicsObject):
    """Volume bars rendered as a custom item."""

    def __init__(self):
        super().__init__()
        self._picture: Optional[QPicture] = None
        self._bounds = QRectF()

    def set_data(self, df: pd.DataFrame):
        self._data = df.reset_index(drop=True)
        self._picture = None
        self._render()
        self.informViewBoundsChanged()
        self.update()

    def dataBounds(self, ax, frac=1.0, orthoRange=None):
        if self._data is None or self._data.empty:
            return None, None
        df = self._data
        if ax == 0:
            return 0, len(df) - 1
        if orthoRange is not None:
            x0, x1 = int(max(0, orthoRange[0])), int(min(len(df) - 1, orthoRange[1]))
            visible = df.iloc[x0:x1 + 1]
            if visible.empty:
                return None, None
        else:
            visible = df
        return float(visible["volume"].min()), float(visible["volume"].max())

    def _render(self):
        if self._data is None or self._data.empty:
            return

        df = self._data
        n = len(df)
        w = 0.3
        max_vol = df["volume"].max()
        self._bounds = QRectF(0, 0, n, max_vol)

        picture = QPicture()
        painter = QPainter(picture)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        brush_up = QBrush(_hex(C_VOLUME_UP))
        brush_dn = QBrush(_hex(C_VOLUME_DN))
        pen_none = QPen(Qt.PenStyle.NoPen)
        painter.setPen(pen_none)

        for i in range(n):
            row = df.iloc[i]
            vol = row["volume"]
            is_bull = row["close"] >= row["open"]
            painter.setBrush(brush_up if is_bull else brush_dn)
            painter.drawRect(QRectF(i - w, 0, 2 * w, vol))

        painter.end()
        self._picture = picture

    def paint(self, painter: QPainter, *args):
        if self._picture:
            painter.drawPicture(0, 0, self._picture)

    def boundingRect(self) -> QRectF:
        return self._bounds


class TimeAxisItem(pg.AxisItem):
    """X-axis that shows datetime labels from DataFrame index."""

    def __init__(self, timestamps=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timestamps: list[str] = timestamps or []
        self.setStyle(tickLength=-5)

    def set_timestamps(self, timestamps: list[str]):
        self._timestamps = timestamps

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(v)
            if 0 <= idx < len(self._timestamps):
                strings.append(self._timestamps[idx])
            else:
                strings.append("")
        return strings


class CandlestickChart(QWidget):
    """
    Complete candlestick chart widget with:
    - Candlestick + wick rendering
    - Volume panel below
    - Moving average overlays (MA20, MA50, MA200)
    - Crosshair cursor
    - Mouse wheel zoom + pan
    - Real-time update via update_last_bar()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._df: Optional[pd.DataFrame] = None
        self._symbol = ""
        self._timeframe = ""
        self._setup_ui()

    # ── Setup ─────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pg.setConfigOptions(
            antialias=False,
            foreground=C_TEXT,
            background=C_BG,
        )

        # GraphicsLayout holds both sub-plots
        self._graphics_layout = pg.GraphicsLayoutWidget()
        self._graphics_layout.setBackground(C_BG)
        layout.addWidget(self._graphics_layout)

        # ── Time axis (shared, at bottom) ──────────────────────────────
        # Non impostare tickFont via setStyle: pyqtgraph crea internamente un
        # font con size=-1 che genera "QFont::setPointSize <= 0" warning su Qt6.
        self._time_axis = TimeAxisItem(orientation="bottom")

        # ── Price plot ─────────────────────────────────────────────────
        self._price_plot = self._graphics_layout.addPlot(
            row=0, col=0,
            axisItems={"bottom": self._time_axis},
        )
        self._price_plot.setMinimumHeight(260)
        self._style_plot(self._price_plot, show_xaxis=False)

        # Candlestick item
        self._candle_item = CandlestickItem()
        self._price_plot.addItem(self._candle_item)

        # Moving averages
        self._ma20_line  = pg.PlotCurveItem(pen=pg.mkPen(C_MA20,  width=1))
        self._ma50_line  = pg.PlotCurveItem(pen=pg.mkPen(C_MA50,  width=1))
        self._ma200_line = pg.PlotCurveItem(pen=pg.mkPen(C_MA200, width=1))
        for line in (self._ma20_line, self._ma50_line, self._ma200_line):
            self._price_plot.addItem(line)

        # Crosshair
        self._v_line = pg.InfiniteLine(angle=90, movable=False,
                                       pen=pg.mkPen(C_CURSOR, width=1, style=Qt.PenStyle.DashLine))
        self._h_line = pg.InfiniteLine(angle=0, movable=False,
                                       pen=pg.mkPen(C_CURSOR, width=1, style=Qt.PenStyle.DashLine))
        self._price_plot.addItem(self._v_line, ignoreBounds=True)
        self._price_plot.addItem(self._h_line, ignoreBounds=True)

        # Crosshair price label
        self._price_label = pg.TextItem("", color=C_CURSOR, anchor=(0, 1))
        self._price_plot.addItem(self._price_label, ignoreBounds=True)

        # ── Volume plot ────────────────────────────────────────────────
        self._vol_plot = self._graphics_layout.addPlot(row=1, col=0)
        self._vol_plot.setMaximumHeight(90)
        self._style_plot(self._vol_plot, show_xaxis=True)
        self._vol_plot.setXLink(self._price_plot)
        self._vol_plot.getAxis("left").setWidth(60)

        self._vol_item = VolumeItem()
        self._vol_plot.addItem(self._vol_item)

        # Row stretch
        self._graphics_layout.ci.layout.setRowStretchFactor(0, 4)
        self._graphics_layout.ci.layout.setRowStretchFactor(1, 1)

        # Mouse move for crosshair
        self._price_plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Auto-update Y range when user pans/zooms (manual because setAutoVisible
        # doesn't work with custom GraphicsObject items lacking dataBounds)
        self._price_plot.getViewBox().sigXRangeChanged.connect(self._on_x_range_changed)

    def _style_plot(self, plot: pg.PlotItem, show_xaxis: bool = True):
        plot.setMenuEnabled(False)
        plot.hideButtons()

        # Background
        plot.getViewBox().setBackgroundColor(C_BG)

        # Grid
        plot.showGrid(x=True, y=True, alpha=0.15)

        # Axis colors
        for axis_name in ("left", "bottom", "right", "top"):
            ax = plot.getAxis(axis_name)
            if ax:
                ax.setPen(pg.mkPen(C_GRID))
                ax.setTextPen(pg.mkPen(C_TEXT))

        plot.getAxis("left").setWidth(60)
        plot.getAxis("bottom").setHeight(22 if show_xaxis else 0)

        if not show_xaxis:
            plot.getAxis("bottom").hide()

        # Enable mouse interaction
        plot.setMouseEnabled(x=True, y=True)

    # ── Public API ────────────────────────────────────────────────────────

    def load_data(self, df: pd.DataFrame, symbol: str = "", timeframe: str = ""):
        """Load a complete OHLCV DataFrame."""
        if df is None or df.empty:
            return

        self._symbol = symbol
        self._timeframe = timeframe
        self._df = df.copy().reset_index()

        # Normalise timestamp column
        if "timestamp" in self._df.columns:
            ts_col = "timestamp"
        elif self._df.columns[0] != "open":
            ts_col = self._df.columns[0]
        else:
            ts_col = None

        # Build human-readable time labels
        if ts_col:
            ts = pd.to_datetime(self._df[ts_col])
            if timeframe in ("1d", "1wk", "1mo"):
                self._time_axis.set_timestamps(ts.dt.strftime("%Y-%m-%d").tolist())
            else:
                self._time_axis.set_timestamps(ts.dt.strftime("%m-%d %H:%M").tolist())

        self._candle_item.set_data(self._df)
        self._vol_item.set_data(self._df)
        self._update_ma_lines()

        # Mostra gli ultimi 120 bar
        n = len(self._df)
        visible_start = max(0, n - 120)
        self._price_plot.setXRange(visible_start - 1, n + 1, padding=0.02)
        # Imposta il range Y manualmente sulle candele visibili
        # (setAutoVisible non funziona con GraphicsObject custom privi di dataBounds)
        self._set_y_range(visible_start, n - 1)

    def update_last_bar(self, bar: dict):
        """Update the last candle with a live tick (call from polling thread)."""
        if self._df is None or self._df.empty:
            return
        last = self._df.index[-1]
        for col in ("open", "high", "low", "close", "volume"):
            if col in bar:
                self._df.at[last, col] = bar[col]
        self._candle_item.set_data(self._df)
        self._vol_item.set_data(self._df)
        self._update_ma_lines()

    def set_ma_visible(self, ma20=True, ma50=True, ma200=True):
        self._ma20_line.setVisible(ma20)
        self._ma50_line.setVisible(ma50)
        self._ma200_line.setVisible(ma200)

    # ── Internals ─────────────────────────────────────────────────────────

    def _update_ma_lines(self):
        if self._df is None:
            return
        closes = self._df["close"].values
        x = np.arange(len(closes), dtype=float)

        def _ma(period: int) -> np.ndarray:
            if len(closes) < period:
                return np.full_like(closes, np.nan, dtype=float)
            kernel = np.ones(period) / period
            full = np.convolve(closes, kernel, mode="full")[:len(closes)]
            result = np.where(x < period - 1, np.nan, full)
            return result

        ma20  = _ma(20)
        ma50  = _ma(50)
        ma200 = _ma(200)

        mask20  = ~np.isnan(ma20)
        mask50  = ~np.isnan(ma50)
        mask200 = ~np.isnan(ma200)

        self._ma20_line.setData(x[mask20],   ma20[mask20])
        self._ma50_line.setData(x[mask50],   ma50[mask50])
        self._ma200_line.setData(x[mask200], ma200[mask200])

    def _set_y_range(self, i0: int, i1: int):
        """Set price plot Y range to fit bars in index range [i0, i1]."""
        if self._df is None or self._df.empty:
            return
        i0 = max(0, i0)
        i1 = min(len(self._df) - 1, i1)
        if i0 > i1:
            return
        visible = self._df.iloc[i0:i1 + 1]
        y_min = float(visible["low"].min())
        y_max = float(visible["high"].max())
        margin = (y_max - y_min) * 0.06
        self._price_plot.setYRange(y_min - margin, y_max + margin, padding=0)

    def _on_x_range_changed(self, _vb, x_range):
        """Called when user pans/zooms — keep Y fitted to visible bars."""
        if self._df is None:
            return
        self._set_y_range(int(x_range[0]), int(x_range[1]))

    def _on_mouse_moved(self, pos):
        if not self._price_plot.sceneBoundingRect().contains(pos):
            return
        mouse_point = self._price_plot.getViewBox().mapSceneToView(pos)
        x = mouse_point.x()
        y = mouse_point.y()
        self._v_line.setPos(x)
        self._h_line.setPos(y)
        self._price_label.setPos(x, y)
        self._price_label.setText(f" {y:.4f}")
