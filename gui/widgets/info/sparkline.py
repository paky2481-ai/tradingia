"""
Sparkline — mini chart compatto senza assi, Bloomberg-grade.

Design:
  - Area gradient sotto la curva (alpha 40) per profondita visiva
  - Polyline con anti-aliasing e round cap
  - Dot sull'ultimo punto, diametro 4px
  - Auto-colore bull/bear basato su diff[-1] - [0]
  - Linea piatta muted se dati < 2 punti
  - Sfondo trasparente, zero overhead
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette semantica ────────────────────────────────────────────────────────
_BULL    = QColor("#3fb950")
_BEAR    = QColor("#f85149")
_NEUTRAL = QColor("#484f58")
_ACCENT  = QColor("#a371f7")


class Sparkline(QWidget):
    """
    Mini-chart a linea polilinea ad alta densita visiva.

    Parametri costruttore:
        width, height   dimensioni fisse (default 80x24)
        color           colore fisso opzionale; se None usa auto bull/bear

    API:
        set_values(values)      lista float, normalizzazione interna min/max
        set_force_color(color)  override colore runtime
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 80,
        height: int = 24,
        color: QColor | None = None,
    ) -> None:
        super().__init__(parent)
        self._w = width
        self._h = height
        self._force_color: QColor | None = color
        self._values: list[float] = []
        self._auto_color: QColor = _BULL

        self.setFixedSize(width, height)
        # Trasparenza reale: niente box background disegnato da Qt
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ── API pubblica ─────────────────────────────────────────────────────────

    def set_values(self, values: list[float]) -> None:
        """Aggiorna la serie e ridisegna. Liste vuote o singolo valore: linea piatta."""
        self._values = list(values)
        if len(self._values) >= 2:
            diff = self._values[-1] - self._values[0]
            self._auto_color = _BULL if diff >= 0 else _BEAR
        else:
            self._auto_color = _NEUTRAL
        last = self._values[-1] if self._values else None
        self.setToolTip(f"{last:.4g}" if last is not None else "—")
        self.update()

    def set_force_color(self, color: QColor | None) -> None:
        """Forza un colore specifico ignorando l'auto-detect."""
        self._force_color = color
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(self._w, self._h)

    # ── Rendering ────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        n = len(self._values)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if n < 2:
            # Linea piatta centrale, colore dim
            pen = QPen(_NEUTRAL, 1.0, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            mid_y = self._h / 2.0
            painter.drawLine(QPointF(2, mid_y), QPointF(self._w - 2, mid_y))
            painter.end()
            return

        color: QColor = self._force_color if self._force_color is not None else self._auto_color

        # Normalizzazione min/max con guard per serie costante
        mn = min(self._values)
        mx = max(self._values)
        span = mx - mn if mx != mn else 1.0

        # Margini: orizzontale minimo per non tagliare il dot finale
        pad_x = 3
        pad_y = 4
        draw_w = self._w - pad_x * 2
        draw_h = self._h - pad_y * 2

        def to_pt(i: int) -> QPointF:
            x = pad_x + (i / (n - 1)) * draw_w
            # Asse Y invertito: alto = massimo
            y = pad_y + (1.0 - (self._values[i] - mn) / span) * draw_h
            return QPointF(x, y)

        points = [to_pt(i) for i in range(n)]

        # ── 1. Area gradient sotto la linea ──────────────────────────────
        path_fill = QPainterPath()
        path_fill.moveTo(QPointF(points[0].x(), self._h - pad_y + 1))
        for pt in points:
            path_fill.lineTo(pt)
        path_fill.lineTo(QPointF(points[-1].x(), self._h - pad_y + 1))
        path_fill.closeSubpath()

        grad = QLinearGradient(0.0, float(pad_y), 0.0, float(self._h))
        fill_top = QColor(color)
        fill_top.setAlpha(50)
        fill_bot = QColor(color)
        fill_bot.setAlpha(0)
        grad.setColorAt(0.0, fill_top)
        grad.setColorAt(1.0, fill_bot)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillPath(path_fill, QBrush(grad))

        # ── 2. Polyline principale ────────────────────────────────────────
        pen_line = QPen(color, 1.5, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen_line)
        path_line = QPainterPath()
        path_line.moveTo(points[0])
        for pt in points[1:]:
            path_line.lineTo(pt)
        painter.drawPath(path_line)

        # ── 3. Dot sull'ultimo punto ──────────────────────────────────────
        last_pt = points[-1]
        # Alone semitrasparente
        halo = QColor(color)
        halo.setAlpha(40)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(last_pt, 4.0, 4.0)
        # Dot pieno
        painter.setBrush(QBrush(color))
        painter.drawEllipse(last_pt, 2.2, 2.2)

        painter.end()
