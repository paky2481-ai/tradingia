"""
PingIndicator — Dot + latency ms + uptime% per stato connessione broker.

Design:
  - Dot 6px colorato (verde/warn/rosso) basato su stato e latency
  - Label "63ms" monospace 10px a destra del dot
  - Uptime piccolo 8px se fornito
  - Rendering custom via QPainter, dimensione ~80px×18px
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette ───────────────────────────────────────────────────────────────────
_GOOD   = QColor("#3fb950")
_WARN   = QColor("#d29922")
_BAD    = QColor("#f85149")
_TEXT   = QColor("#e6edf3")
_MUTED  = QColor("#a8b1bb")
_DIM    = QColor("#6e7681")

_LATENCY_WARN_MS = 200


class PingIndicator(QWidget):
    """
    Indicatore ping con dot colorato, latency e uptime%.

    API:
        set_state(connected, latency_ms, uptime_pct)

    Uso:
        ping = PingIndicator()
        ping.set_state(True, 63, 99.9)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._connected: bool = False
        self._latency_ms: int = 0
        self._uptime_pct: float = 100.0

        self.setMinimumSize(80, 18)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._update_tooltip()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_state(
        self,
        connected: bool,
        latency_ms: int = 0,
        uptime_pct: float = 100.0,
    ) -> None:
        """Aggiorna lo stato del ping indicator."""
        self._connected = connected
        self._latency_ms = max(0, int(latency_ms))
        self._uptime_pct = max(0.0, min(100.0, float(uptime_pct)))
        self._update_tooltip()
        self.update()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _dot_color(self) -> QColor:
        if not self._connected:
            return _BAD
        if self._latency_ms > _LATENCY_WARN_MS:
            return _WARN
        return _GOOD

    def _update_tooltip(self) -> None:
        if not self._connected:
            self.setToolTip("Broker disconnesso")
        else:
            self.setToolTip(
                f"Broker connesso · {self._latency_ms}ms · "
                f"{self._uptime_pct:.1f}% uptime ultime 24h"
            )

    def _font_latency(self) -> QFont:
        f = QFont()
        f.setFamilies(["Consolas", "Cascadia Code", "JetBrains Mono", "monospace"])
        f.setPixelSize(10)
        f.setWeight(QFont.Weight.Medium)
        return f

    def _font_uptime(self) -> QFont:
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "sans-serif"])
        f.setPixelSize(8)
        return f

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())
        h = float(self.height())
        cy = h / 2.0

        dot_r = 3.0
        dot_x = 4.0 + dot_r  # centro dot x

        # ── Dot ───────────────────────────────────────────────────────────────
        col = self._dot_color()

        # Glow sottile
        glow = QColor(col)
        glow.setAlpha(35)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(dot_x, cy), dot_r + 2.5, dot_r + 2.5)

        painter.setBrush(QBrush(col))
        painter.drawEllipse(QPointF(dot_x, cy), dot_r, dot_r)

        # ── Label latency ─────────────────────────────────────────────────────
        x_text = dot_x + dot_r + 5.0

        if self._connected:
            painter.setFont(self._font_latency())
            painter.setPen(_TEXT)
            lat_text = f"{self._latency_ms}ms"
            lat_rect = QRectF(x_text, 0.0, w - x_text, h * 0.72)
            painter.drawText(
                lat_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                lat_text,
            )

            # Uptime piccolo sotto/accanto
            painter.setFont(self._font_uptime())
            painter.setPen(_DIM)
            up_text = f"{self._uptime_pct:.1f}%"
            # Stima larghezza approssimativa del testo latency per posizionare uptime
            lat_w = len(lat_text) * 6.5
            up_rect = QRectF(x_text + lat_w + 3.0, 0.0, w, h)
            painter.drawText(
                up_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                up_text,
            )
        else:
            painter.setFont(self._font_latency())
            painter.setPen(_DIM)
            rect = QRectF(x_text, 0.0, w - x_text, h)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "---",
            )

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(80, 18)
