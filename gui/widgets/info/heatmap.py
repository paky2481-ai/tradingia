"""
Heatmap — Matrice colorata per correlazioni N×N.

Design:
  - Cell colorate: rosso scuro (-1) → grigio (0) → verde scuro (+1)
  - Label perimetrali lungo top e left, 9px
  - Testo valore in ogni cell se cell >= 40px
  - Tooltip via mouseMoveEvent: "ASSET_A vs ASSET_B: 0.82"
  - Dimensioni minime 120x120, aspect ratio preferibilmente quadrato
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette di base ───────────────────────────────────────────────────────────
_BG         = QColor("#0d1117")
_CELL_NEG   = QColor("#7d1b17")   # rosso scuro per -1
_CELL_ZERO  = QColor("#21262d")   # grigio neutro per 0
_CELL_POS   = QColor("#1a4a2e")   # verde scuro per +1
_DIAG       = QColor("#2d333b")   # diagonale
_TEXT_LIGHT = QColor("#e6edf3")
_TEXT_DIM   = QColor("#6e7681")
_LABEL_AREA = 22  # px area label perimetrale


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    """Interpolazione lineare tra due QColor (t in [0,1])."""
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
    )


def _cell_color(value: float) -> QColor:
    """Mappa [-1, 1] → colore cella."""
    v = max(-1.0, min(1.0, float(value)))
    if v < 0.0:
        return _lerp_color(_CELL_ZERO, _CELL_NEG, -v)
    elif v > 0.0:
        return _lerp_color(_CELL_ZERO, _CELL_POS, v)
    else:
        return _CELL_ZERO


class Heatmap(QWidget):
    """
    Matrice di correlazione N×N con colori semantici.

    API:
        set_matrix(values, labels)   N×N square, valori in [-1, 1]

    Uso:
        hm = Heatmap()
        hm.set_matrix(
            [[1.0, 0.82, -0.3], [0.82, 1.0, 0.1], [-0.3, 0.1, 1.0]],
            ["BTC", "ETH", "SPX"],
        )
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._matrix: list[list[float]] = []
        self._labels: list[str] = []
        self._n: int = 0

        # Tracciamo l'ultima cella hovered per tooltip
        self._hover_cell: tuple[int, int] | None = None

        self.setMinimumSize(120, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_matrix(self, values: list[list[float]], labels: list[str]) -> None:
        """Imposta la matrice N×N e le etichette."""
        n = len(labels)
        if n == 0 or len(values) != n:
            return
        self._n = n
        self._labels = list(labels)
        self._matrix = [list(row[:n]) for row in values[:n]]
        self.update()

    # ── Helpers geometria ─────────────────────────────────────────────────────

    def _cell_size(self) -> tuple[float, float]:
        """(cell_w, cell_h) in pixel."""
        if self._n == 0:
            return (0.0, 0.0)
        area_w = float(self.width())  - float(_LABEL_AREA)
        area_h = float(self.height()) - float(_LABEL_AREA)
        return (area_w / self._n, area_h / self._n)

    def _cell_at_pos(self, px: int, py: int) -> tuple[int, int] | None:
        """Ritorna (row, col) dalla posizione pixel, o None."""
        if self._n == 0:
            return None
        cw, ch = self._cell_size()
        if cw <= 0 or ch <= 0:
            return None
        cx = (px - _LABEL_AREA) / cw
        cy = (py - _LABEL_AREA) / ch
        col = int(cx)
        row = int(cy)
        if 0 <= row < self._n and 0 <= col < self._n:
            return (row, col)
        return None

    def _font_label(self) -> QFont:
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "sans-serif"])
        f.setPixelSize(9)
        return f

    def _font_value(self) -> QFont:
        f = QFont()
        f.setFamilies(["Consolas", "Cascadia Code", "monospace"])
        f.setPixelSize(9)
        return f

    # ── Mouse events ──────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        cell = self._cell_at_pos(event.position().x(), event.position().y())
        if cell != self._hover_cell:
            self._hover_cell = cell
            if cell is not None:
                r, c = cell
                a = self._labels[r] if r < len(self._labels) else str(r)
                b = self._labels[c] if c < len(self._labels) else str(c)
                val = self._matrix[r][c]
                self.setToolTip(f"{a} vs {b}: {val:.2f}")
            else:
                self.setToolTip("")

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_cell = None
        super().leaveEvent(event)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._n == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        cw, ch = self._cell_size()
        la = float(_LABEL_AREA)

        # ── Label colonne (top) ───────────────────────────────────────────────
        painter.setFont(self._font_label())
        painter.setPen(_TEXT_DIM)
        for c in range(self._n):
            lbl = self._labels[c] if c < len(self._labels) else str(c)
            rx = la + c * cw
            label_rect = QRectF(rx, 0.0, cw, la)
            # Truncate se troppo corto
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                lbl[:5],
            )

        # ── Label righe (left) ────────────────────────────────────────────────
        for r in range(self._n):
            lbl = self._labels[r] if r < len(self._labels) else str(r)
            ry = la + r * ch
            label_rect = QRectF(0.0, ry, la - 2.0, ch)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                lbl[:5],
            )

        # ── Celle ─────────────────────────────────────────────────────────────
        painter.setPen(Qt.PenStyle.NoPen)
        show_text = (cw >= 38.0 and ch >= 16.0)

        for r in range(self._n):
            for c in range(self._n):
                val = self._matrix[r][c] if c < len(self._matrix[r]) else 0.0
                rx = la + c * cw
                ry = la + r * ch
                cell_rect = QRectF(rx + 0.5, ry + 0.5, cw - 1.0, ch - 1.0)

                # Diagonale: sfondo diverso
                if r == c:
                    painter.setBrush(QBrush(_DIAG))
                else:
                    painter.setBrush(QBrush(_cell_color(val)))
                painter.drawRect(cell_rect)

                # Testo valore
                if show_text:
                    painter.setFont(self._font_value())
                    text_col = QColor(_TEXT_LIGHT)
                    text_col.setAlpha(200)
                    painter.setPen(text_col)
                    painter.drawText(
                        cell_rect,
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                        f"{val:.2f}",
                    )
                    painter.setPen(Qt.PenStyle.NoPen)

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(180, 180)
