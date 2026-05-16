"""
ConfidenceBar — Barra orizzontale 0-1 con threshold marker visivo.

Design:
  - Background pill arrotondato BG_ELEVATED
  - Fill colorato in base al valore: rosso < 0.5, warn 0.5-threshold, verde >= threshold
  - Threshold marker: linea verticale tratteggiata 2px
  - Testo valore monospace 11px a destra
  - Label opzionale sopra la barra
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette ───────────────────────────────────────────────────────────────────
_BG_ELEVATED = QColor("#21262d")
_BG_BASE     = QColor("#0d1117")
_TEXT        = QColor("#e6edf3")
_MUTED       = QColor("#a8b1bb")
_DIM         = QColor("#6e7681")
_BULL        = QColor("#3fb950")
_BEAR        = QColor("#f85149")
_WARN        = QColor("#d29922")

# Costanti layout
_LABEL_H = 13
_PAD_Y   = 2    # gap label-barra
_TRACK_H = 10
_PAD_X   = 4
_TOTAL_H = _LABEL_H + _PAD_Y + _TRACK_H


class ConfidenceBar(QWidget):
    """
    Barra orizzontale confidence 0-1 con threshold marker.

    API:
        set_value(v: float)       range [0.0, 1.0], clamp se fuori
        set_threshold(t: float)   soglia "affidabile" (default 0.7)
        set_label(text: str|None) etichetta opzionale sopra la barra

    Uso:
        cb = ConfidenceBar()
        cb.set_label("CONFIDENCE")
        cb.set_threshold(0.7)
        cb.set_value(0.78)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value: float = 0.0
        self._threshold: float = 0.7
        self._label: str | None = None

        self.setMinimumSize(120, _TOTAL_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_TOTAL_H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._update_tooltip()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_value(self, v: float) -> None:
        self._value = max(0.0, min(1.0, float(v)))
        self._update_tooltip()
        self.update()

    def set_threshold(self, t: float = 0.7) -> None:
        self._threshold = max(0.0, min(1.0, float(t)))
        self._update_tooltip()
        self.update()

    def set_label(self, text: str | None) -> None:
        self._label = text
        self.update()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fill_color(self) -> QColor:
        if self._value >= self._threshold:
            return _BULL
        elif self._value >= 0.5:
            return _WARN
        else:
            return _BEAR

    def _update_tooltip(self) -> None:
        self.setToolTip(
            f"Confidence: {self._value * 100:.0f}% "
            f"(threshold: {self._threshold * 100:.0f}%)"
        )

    def _font_label(self) -> QFont:
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "sans-serif"])
        f.setPixelSize(9)
        f.setWeight(QFont.Weight.Medium)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
        return f

    def _font_value(self) -> QFont:
        f = QFont()
        f.setFamilies(["Consolas", "Cascadia Code", "JetBrains Mono", "monospace"])
        f.setPixelSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())

        # Larghezza utile del track (lasciamo spazio al valore numerico a dx)
        val_w = 36.0   # spazio per "0.78" monospace 11px
        tx1 = float(_PAD_X)
        tx2 = w - float(_PAD_X) - val_w - 4.0
        tw  = max(10.0, tx2 - tx1)

        fill_col = self._fill_color()

        # ── Riga label (opzionale) ────────────────────────────────────────────
        if self._label:
            painter.setFont(self._font_label())
            painter.setPen(_MUTED)
            label_rect = QRectF(tx1, 0.0, tw, float(_LABEL_H))
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._label.upper(),
            )

        # Calcolo y track
        track_top = float(_LABEL_H + _PAD_Y) if self._label else float(_PAD_Y)
        track_rect = QRectF(tx1, track_top, tw, float(_TRACK_H))
        r = float(_TRACK_H) / 2.0

        # ── Background track pill ─────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_BG_ELEVATED)
        painter.drawRoundedRect(track_rect, r, r)

        # ── Fill ──────────────────────────────────────────────────────────────
        fill_w = self._value * tw
        if fill_w > 0.5:
            clip = QPainterPath()
            clip.addRoundedRect(track_rect, r, r)
            painter.setClipPath(clip)

            fill_col_alpha = QColor(fill_col)
            fill_col_alpha.setAlpha(200)
            painter.setBrush(fill_col_alpha)
            painter.drawRect(QRectF(tx1, track_top, fill_w, float(_TRACK_H)))
            painter.setClipping(False)

        # ── Threshold marker ──────────────────────────────────────────────────
        th_x = tx1 + self._threshold * tw
        th_pen = QPen(_DIM, 1.5, Qt.PenStyle.DashLine)
        th_pen.setDashPattern([2.0, 2.0])
        painter.setPen(th_pen)
        painter.drawLine(
            QRectF(th_x, track_top - 1.0, 0.0, float(_TRACK_H) + 2.0).topLeft(),
            QRectF(th_x, track_top - 1.0, 0.0, float(_TRACK_H) + 2.0).bottomLeft(),
        )

        # ── Valore numerico a destra ──────────────────────────────────────────
        painter.setFont(self._font_value())
        painter.setPen(fill_col)
        val_rect = QRectF(
            w - val_w - float(_PAD_X),
            track_top - 1.0,
            val_w,
            float(_TRACK_H) + 2.0,
        )
        painter.drawText(
            val_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self._value:.2f}",
        )

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(160, _TOTAL_H)
