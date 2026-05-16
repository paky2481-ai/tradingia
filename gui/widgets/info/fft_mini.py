"""
FFTMini — Spettro frequenze compatto 120x40 con peak marker.

Design:
  - Barre verticali magnitude normalizzata 0-1
  - Gradiente blu (INFO) per ampiezze basse → ciano per alte
  - Peak marker: triangolo invertito sopra la barra di picco ACCENT
  - Titolo opzionale 9px sopra il plot
  - Sfondo trasparente
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette ───────────────────────────────────────────────────────────────────
_INFO      = QColor("#1f6feb")
_INFO_CYAN = QColor("#56d4dd")
_ACCENT    = QColor("#a371f7")
_TEXT_DIM  = QColor("#6e7681")


class FFTMini(QWidget):
    """
    Mini spettro FFT 120x40px.

    API:
        set_spectrum(magnitudes, peak_idx)   lista float [0-1], indice picco
        set_title(text)                       testo opzionale sopra il plot

    Uso:
        fft = FFTMini()
        fft.set_title("FFT 50 bars")
        fft.set_spectrum([0.1, 0.4, 0.8, 0.3, 0.6], peak_idx=2)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._magnitudes: list[float] = []
        self._peak_idx: int | None = None
        self._title: str = ""

        self.setMinimumSize(80, 32)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_spectrum(
        self,
        magnitudes: list[float],
        peak_idx: int | None = None,
    ) -> None:
        self._magnitudes = [max(0.0, min(1.0, float(m))) for m in magnitudes]
        # Auto-detect peak se non fornito
        if peak_idx is None and self._magnitudes:
            self._peak_idx = self._magnitudes.index(max(self._magnitudes))
        else:
            self._peak_idx = peak_idx
        # Tooltip
        if self._peak_idx is not None and self._magnitudes:
            amp = self._magnitudes[self._peak_idx]
            self.setToolTip(f"Picco: bin {self._peak_idx} · ampiezza {amp:.2f}")
        self.update()

    def set_title(self, text: str) -> None:
        self._title = text
        self.update()

    # ── Font helpers ──────────────────────────────────────────────────────────

    def _font_title(self) -> QFont:
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "sans-serif"])
        f.setPixelSize(9)
        return f

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())
        h = float(self.height())

        # Area titolo
        title_h = 10.0 if self._title else 0.0
        plot_top = title_h + (2.0 if self._title else 0.0)
        plot_h = h - plot_top

        # ── Titolo ────────────────────────────────────────────────────────────
        if self._title:
            painter.setFont(self._font_title())
            painter.setPen(_TEXT_DIM)
            painter.drawText(
                QRectF(0.0, 0.0, w, title_h + 2.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._title,
            )

        n = len(self._magnitudes)
        if n < 1:
            painter.end()
            return

        # Larghezza barra + gap
        gap = 1.0
        bar_w = max(1.0, (w - gap * (n - 1)) / n)

        # ── Barre ────────────────────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)

        for i, mag in enumerate(self._magnitudes):
            bar_h = max(2.0, mag * (plot_h - 4.0))
            bx = i * (bar_w + gap)
            by = plot_top + (plot_h - bar_h)

            # Gradiente per barra (blu basso → ciano alto)
            grad = QLinearGradient(bx, by + bar_h, bx, by)
            grad.setColorAt(0.0, _INFO)
            grad.setColorAt(1.0, _INFO_CYAN)

            painter.setBrush(QBrush(grad))
            painter.drawRect(QRectF(bx, by, bar_w, bar_h))

        # ── Peak marker: triangolo invertito ACCENT ───────────────────────────
        if self._peak_idx is not None and 0 <= self._peak_idx < n:
            mag_peak = self._magnitudes[self._peak_idx]
            bar_h_peak = max(2.0, mag_peak * (plot_h - 4.0))
            bx_peak = self._peak_idx * (bar_w + gap)
            bar_top_y = plot_top + (plot_h - bar_h_peak)
            cx = bx_peak + bar_w / 2.0
            ty = bar_top_y - 5.0  # sopra la barra

            # Triangolo invertito (vertice in basso)
            tri_size = 4.0
            triangle = QPolygonF([
                QPointF(cx - tri_size, ty - tri_size * 1.3),
                QPointF(cx + tri_size, ty - tri_size * 1.3),
                QPointF(cx, ty),
            ])
            painter.setBrush(QBrush(_ACCENT))
            painter.drawPolygon(triangle)

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(120, 44)
