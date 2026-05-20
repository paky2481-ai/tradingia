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
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QPicture, QPen, QBrush, QColor, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

# ── Colors ────────────────────────────────────────────────────────────────
C_BG        = "#0d1117"
C_BG2       = "#161b22"
C_GRID      = "#21262d"
C_TEXT      = "#a8b1bb"
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

        for i in range(n):
            row = df.iloc[i]
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            is_bull = c >= o

            pen = pen_bull if is_bull else pen_bear
            painter.setPen(pen)

            # Wick — solo se ha un'estensione reale. Una wick degenere
            # (high == low, es. barra forex senza range) diventa un drawLine
            # da un punto a se stesso che, sotto la scala forex nel QPicture,
            # degenera e copre l'intero grafico con una barra verticale.
            if h > l:
                painter.drawLine(
                    pg.Point(i, l),
                    pg.Point(i, h),
                )

            # Body
            body_top = max(o, c)
            body_bot = min(o, c)
            body_h = body_top - body_bot

            # Doji (body nullo): un body a spessore zero sarebbe invisibile.
            # Forza uno spessore minimo visibile centrato sul prezzo.
            if body_h < 1e-10:
                body_h = (max_price - min_price) * 0.01
                body_bot = c - body_h / 2

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
        self._data: Optional[pd.DataFrame] = None
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
    """X-axis with adaptive datetime labels that respond to zoom level.

    Internamente tiene una lista di pd.Timestamp (datetime reali).
    tickStrings() sceglie il formato in base all'arco temporale fra due tick
    (spacing in barre × durata per barra), implementando sia il formato
    adattivo per fascia che il contesto gerarchico ai confini di unità.
    """

    # Mesi abbreviati in italiano
    _MESI_IT = ["", "Gen", "Feb", "Mar", "Apr", "Mag", "Giu",
                "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]

    def __init__(self, timestamps=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Accetta sia list[str] (retrocompatibilità) che list[pd.Timestamp]
        self._timestamps: list = []
        self._bar_seconds: float = 3600.0   # default: 1h
        self.setStyle(tickLength=-5)
        if timestamps is not None:
            self.set_timestamps(timestamps)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_timestamps(self, timestamps):
        """Accetta list[pd.Timestamp], pd.DatetimeIndex, o list[str] (legacy)."""
        if timestamps is None:
            self._timestamps = []
            return
        if len(timestamps) == 0:
            self._timestamps = []
            return
        first = timestamps[0]
        if isinstance(first, str):
            # Legacy: stringa già formattata — teniamo as-is, non usiamo formato adattivo
            self._timestamps = list(timestamps)
        else:
            # pd.Timestamp o datetime — converti a lista
            self._timestamps = list(pd.Timestamp(t) if not isinstance(t, pd.Timestamp) else t
                                    for t in timestamps)

    def set_timeframe(self, timeframe: str):
        """Calcola durata per barra in secondi dal timeframe (es. '1h', '1d')."""
        mapping = {
            "1m": 60,        "3m": 180,       "5m": 300,
            "15m": 900,      "30m": 1800,
            "1h": 3600,      "2h": 7200,      "4h": 14400,
            "6h": 21600,     "8h": 28800,     "12h": 43200,
            "1d": 86400,     "1w": 604800,    "1wk": 604800,
            "1mo": 2592000,  "1M": 2592000,
        }
        self._bar_seconds = float(mapping.get(timeframe, 3600))

    def timestamp_at(self, idx: int) -> "pd.Timestamp | None":
        """Restituisce il timestamp all'indice idx, o None se fuori range."""
        if not self._timestamps:
            return None
        if not isinstance(self._timestamps[0], pd.Timestamp):
            return None
        idx = int(idx)
        if 0 <= idx < len(self._timestamps):
            return self._timestamps[idx]
        return None

    # ── Formato adattivo ────────────────────────────────────────────────────

    def _fmt_month(self, m: int) -> str:
        """Restituisce il mese abbreviato in italiano."""
        return self._MESI_IT[m] if 1 <= m <= 12 else f"{m:02d}"

    def _format_label(self, ts: "pd.Timestamp", arc_seconds: float,
                      prev_ts: "pd.Timestamp | None") -> str:
        """Formato adattivo con contesto gerarchico ai confini di unità.

        arc_seconds: arco temporale in secondi fra due tick adiacenti.
        prev_ts: timestamp del tick precedente (per rilevare cambio di unità).

        Fasce:
          >= 365 d  → solo anno (es. "2025")
          >= 25 d   → mese + anno (es. "Gen 2025");
                      se cambio anno mostra l'anno in evidenza
          >= 20 h   → giorno + mese (es. "15 Gen");
                      al confine di anno aggiunge l'anno
          < 20 h    → "15 Gen 14:00";
                      se il giorno non cambia rispetto al prev mostra "14:00"
                      al confine di giorno mostra "15 Gen 14:00"
        """
        GIORNO = 86400
        ORA = 3600

        if arc_seconds >= 365 * GIORNO:
            # Fascia annuale
            label = str(ts.year)
            return label

        if arc_seconds >= 25 * GIORNO:
            # Fascia mensile
            base = f"{self._fmt_month(ts.month)} {ts.year}"
            if prev_ts is not None and prev_ts.year != ts.year:
                return str(ts.year)   # confine anno: metti in evidenza solo anno
            return base

        if arc_seconds >= 20 * ORA:
            # Fascia giornaliera
            base = f"{ts.day} {self._fmt_month(ts.month)}"
            if prev_ts is not None and prev_ts.year != ts.year:
                return f"{ts.day} {self._fmt_month(ts.month)} {ts.year}"
            return base

        # Fascia intra-day
        time_part = f"{ts.hour:02d}:{ts.minute:02d}"
        if prev_ts is None:
            return f"{ts.day} {self._fmt_month(ts.month)} {time_part}"
        if prev_ts.date() != ts.date():
            # Confine giorno — aggiungi data per contesto
            return f"{ts.day} {self._fmt_month(ts.month)} {time_part}"
        return time_part

    def tickStrings(self, values, scale, spacing):
        # Se la lista contiene stringhe (legacy), comportamento invariato
        if not self._timestamps or (
                len(self._timestamps) > 0 and isinstance(self._timestamps[0], str)):
            strings = []
            for v in values:
                idx = int(v)
                if 0 <= idx < len(self._timestamps):
                    strings.append(self._timestamps[idx])
                else:
                    strings.append("")
            return strings

        # spacing è in "unità barra" — moltiplicato per la durata per barra dà secondi
        arc_seconds = float(spacing) * self._bar_seconds

        strings = []
        prev_ts = None
        for v in values:
            idx = int(v)
            if 0 <= idx < len(self._timestamps):
                ts = self._timestamps[idx]
                label = self._format_label(ts, arc_seconds, prev_ts)
                strings.append(label)
                prev_ts = ts
            else:
                strings.append("")
        return strings


class VolumeAxisItem(pg.AxisItem):
    """Y-axis for volume that formats large numbers as K/M instead of SI notation."""

    def tickStrings(self, values, scale, spacing):
        result = []
        for v in values:
            av = abs(v)
            if av >= 1_000_000:
                result.append(f"{v / 1_000_000:.1f}M")
            elif av >= 1_000:
                result.append(f"{v / 1_000:.0f}K")
            else:
                result.append(f"{int(v)}")
        return result


class PriceAxisItem(pg.AxisItem):
    """Y-axis for price: always 3 decimal places, independent of zoom/range."""

    def tickStrings(self, values, scale, spacing):
        return [f"{v:.3f}" for v in values]


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

    # Emitted on mouse hover with bar data dict
    bar_hovered = pyqtSignal(dict)

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
            axisItems={
                "bottom": self._time_axis,
                "left":   PriceAxisItem(orientation="left"),
                "right":  PriceAxisItem(orientation="right"),
            },
        )
        self._price_plot.setMinimumHeight(260)
        self._style_plot(self._price_plot, show_xaxis=False)
        self._price_plot.showAxis("right")
        self._price_plot.getAxis("right").setWidth(55)
        self._price_plot.getAxis("right").setPen(pg.mkPen(C_GRID))
        self._price_plot.getAxis("right").setTextPen(pg.mkPen(C_TEXT))

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

        # Right-axis cursor price label (yellow box, segue cursore sull'asse Y)
        self._cursor_price_label = pg.TextItem("", anchor=(0, 0.5), color="#0d1117")
        self._cursor_price_label.fill = pg.mkBrush("#e3b341")
        _font_price = QFont("monospace", 9)
        self._cursor_price_label.setFont(_font_price)
        self._price_plot.addItem(self._cursor_price_label, ignoreBounds=True)

        # OHLC tooltip (segue cursore, sfondo scuro, font leggibile)
        self._price_label = pg.TextItem("", anchor=(0, 1), color="#e6edf3")
        self._price_label.fill = pg.mkBrush(13, 17, 23, 210)
        self._price_label.setFont(QFont("monospace", 9))
        self._price_plot.addItem(self._price_label, ignoreBounds=True)

        # ── Volume plot ────────────────────────────────────────────────
        self._vol_time_axis = TimeAxisItem(orientation="bottom")
        self._vol_plot = self._graphics_layout.addPlot(
            row=1, col=0,
            axisItems={
                "bottom": self._vol_time_axis,
                "left":   VolumeAxisItem(orientation="left"),
            },
        )
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

        # Passa datetime reali agli assi per etichette adattive allo zoom.
        # set_timeframe() configura la durata per barra usata da tickStrings().
        if ts_col:
            ts_series = pd.to_datetime(self._df[ts_col])
            dt_list = ts_series.tolist()   # list[pd.Timestamp]
            for ax in (self._time_axis, self._vol_time_axis):
                ax.set_timestamps(dt_list)
                ax.set_timeframe(timeframe)

        self._candle_item.set_data(self._df)
        self._vol_item.set_data(self._df)
        self._update_ma_lines()

        # Mostra gli ultimi 120 bar
        n = len(self._df)
        visible_start = max(0, n - 120)

        # Limit panning to actual data range
        self._price_plot.getViewBox().setLimits(xMin=-1, xMax=n)

        self._price_plot.setXRange(visible_start - 1, n + 1, padding=0.02)
        # Imposta il range Y manualmente sulle candele visibili
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
        vb = self._price_plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        y = mouse_point.y()
        self._v_line.setPos(x)
        self._h_line.setPos(y)

        # Label prezzo sull'asse Y destro (segue solo il cursore verticale)
        x_range = vb.viewRange()[0]
        self._cursor_price_label.setPos(x_range[1], y)
        self._cursor_price_label.setText(f" {y:.3f} ")

        idx = int(round(x))
        if self._df is not None and 0 <= idx < len(self._df):
            row = self._df.iloc[idx]
            # Ricava la stringa data dal timestamp reale (massimo contesto per il tooltip)
            ts_obj = self._time_axis.timestamp_at(idx)
            if ts_obj is not None:
                # Tooltip: sempre data + ora completa per massima chiarezza
                if ts_obj.hour == 0 and ts_obj.minute == 0:
                    date_str = ts_obj.strftime("%Y-%m-%d")
                else:
                    date_str = ts_obj.strftime("%Y-%m-%d %H:%M")
            else:
                raw = self._time_axis._timestamps
                entry = raw[idx] if 0 <= idx < len(raw) else ""
                date_str = entry if isinstance(entry, str) else str(entry)
            # OHLC tooltip vicino al cursore (in alto a sinistra rispetto al cursore)
            self._price_label.setPos(x, y)
            self._price_label.setText(
                f"  {date_str}   C: {row['close']:.3f}"
                f"   O: {row['open']:.3f}   H: {row['high']:.3f}   L: {row['low']:.3f}  "
            )
            self.bar_hovered.emit({
                "date":   date_str,
                "open":   float(row["open"]),
                "high":   float(row["high"]),
                "low":    float(row["low"]),
                "close":  float(row["close"]),
                "volume": float(row.get("volume", 0)),
            })
        else:
            self._price_label.setPos(x, y)
            self._price_label.setText(f"  {y:.3f}  ")
