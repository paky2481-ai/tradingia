"""
BiDirectionalBar — Barra split centro per bull/bear sentiment.

Design:
  - Centro = punto neutro
  - Bull (verde) cresce a destra, Bear (rosso) cresce a sinistra
  - Etichette piccole 9px con percentuali su ciascun lato
  - Background BG_ELEVATED, pill arrotondato
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette ───────────────────────────────────────────────────────────────────
_BG_ELEVATED = QColor("#21262d")
_BULL        = QColor("#3fb950")
_BEAR        = QColor("#f85149")
_DIM         = QColor("#6e7681")

# Costanti layout
_LABEL_H = 12   # area etichette testo
_PAD_Y   = 2    # gap etichette-barra
_TRACK_H = 8
_PAD_X   = 2
_TOTAL_H = _LABEL_H + _PAD_Y + _TRACK_H


class BiDirectionalBar(QWidget):
    """
    Barra bull/bear con split dal centro.

    API:
        set_split(bull, bear)         normalizza a somma=1
        set_labels(left, right)       override etichette (default BEAR / BULL)

    Uso:
        bar = BiDirectionalBar()
        bar.set_split(0.65, 0.35)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bull: float = 0.5
        self._bear: float = 0.5
        self._left_label: str = "BEAR"
        self._right_label: str = "BULL"

        self.setMinimumSize(140, _TOTAL_H)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_TOTAL_H)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._update_tooltip()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_split(self, bull: float, bear: float) -> None:
        """Imposta bull/bear. Normalizza a somma=1 automaticamente."""
        total = bull + bear
        if total <= 0:
            self._bull = 0.5
            self._bear = 0.5
        else:
            self._bull = bull / total
            self._bear = bear / total
        self._update_tooltip()
        self.update()

    def set_labels(self, left: str = "BEAR", right: str = "BULL") -> None:
        self._left_label = left
        self._right_label = right
        self.update()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _update_tooltip(self) -> None:
        self.setToolTip(
            f"Long: {self._bull * 100:.0f}% · Short: {self._bear * 100:.0f}%"
        )

    def _font_label(self) -> QFont:
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "sans-serif"])
        f.setPixelSize(9)
        f.setWeight(QFont.Weight.Medium)
        return f

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self.width())

        tx1 = float(_PAD_X)
        tx2 = w - float(_PAD_X)
        tw  = max(10.0, tx2 - tx1)

        track_top = float(_LABEL_H + _PAD_Y)
        r = float(_TRACK_H) / 2.0
        track_rect = QRectF(tx1, track_top, tw, float(_TRACK_H))
        center_x = tx1 + tw / 2.0

        # ── Background track ──────────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_BG_ELEVATED)
        painter.drawRoundedRect(track_rect, r, r)

        # ── Clip per fill arrotondato ─────────────────────────────────────────
        clip = QPainterPath()
        clip.addRoundedRect(track_rect, r, r)
        painter.setClipPath(clip)

        # ── Fill BEAR: cresce a sinistra dal centro ────────────────────────────
        bear_w = self._bear * (tw / 2.0)
        if bear_w > 0.5:
            bc = QColor(_BEAR)
            bc.setAlpha(200)
            painter.setBrush(bc)
            painter.drawRect(QRectF(center_x - bear_w, track_top, bear_w, float(_TRACK_H)))

        # ── Fill BULL: cresce a destra dal centro ─────────────────────────────
        bull_w = self._bull * (tw / 2.0)
        if bull_w > 0.5:
            gc = QColor(_BULL)
            gc.setAlpha(200)
            painter.setBrush(gc)
            painter.drawRect(QRectF(center_x, track_top, bull_w, float(_TRACK_H)))

        painter.setClipping(False)

        # ── Linea centrale marker ─────────────────────────────────────────────
        from PyQt6.QtGui import QPen
        from PyQt6.QtCore import QPointF
        painter.setPen(QPen(QColor("#30363d"), 1.0, Qt.PenStyle.SolidLine))
        painter.drawLine(
            QPointF(center_x, track_top),
            QPointF(center_x, track_top + float(_TRACK_H)),
        )

        # ── Etichette testo ───────────────────────────────────────────────────
        painter.setFont(self._font_label())

        # BEAR sx
        bear_pct = f"{self._left_label} {self._bear * 100:.0f}%"
        bear_rect = QRectF(tx1, 0.0, tw / 2.0, float(_LABEL_H))
        painter.setPen(QColor(_BEAR))
        painter.drawText(
            bear_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            bear_pct,
        )

        # BULL dx
        bull_pct = f"{self._right_label} {self._bull * 100:.0f}%"
        bull_rect = QRectF(tx1 + tw / 2.0, 0.0, tw / 2.0, float(_LABEL_H))
        painter.setPen(QColor(_BULL))
        painter.drawText(
            bull_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            bull_pct,
        )

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(160, _TOTAL_H)
