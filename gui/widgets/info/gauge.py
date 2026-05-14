"""
Gauge — barra orizzontale 0-1 con zone colorate e marker di posizione.

Uso primario: Hurst exponent, Kelly fraction, confidence score, RSI normalizzato.

Design:
  - Track pill arrotondato (altezza 8px) con sfondo BG_ELEVATED
  - Zone colorate semi-trasparenti (alpha 55) come fasce di sfondo
  - Fill colorato dal bordo sinistro fino al valore (colore zona attiva, alpha 200)
  - Marker: linea verticale 1.5px + cerchio pieno diametro 6px, colore zona attiva
  - Label 9px uppercase muted in alto a sinistra
  - Valore numerico 9px monospace colorato (colore zona) in alto a destra
  - Tutto il rendering via QPainter: zero overhead QProgressBar
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget


# ── Palette ───────────────────────────────────────────────────────────────────
_BG_ELEVATED = "#21262d"
_TRACK_BG    = "#161b22"
_TEXT        = "#e6edf3"
_MUTED       = "#8b949e"
_BULL        = "#3fb950"
_BEAR        = "#f85149"
_WARN        = "#d29922"

# Zone default (Hurst exponent):
#   0.0 – 0.4  mean-reverting  (rosso)
#   0.4 – 0.6  random walk     (giallo)
#   0.6 – 1.0  trending        (verde)
_DEFAULT_ZONES: list[tuple[float, float, str]] = [
    (0.0, 0.4, _BEAR),
    (0.4, 0.6, _WARN),
    (0.6, 1.0, _BULL),
]

# Costanti layout
_LABEL_H     = 13   # altezza area testo label + valore
_PAD_BETWEEN = 3    # gap tra label row e track
_TRACK_H     = 8    # altezza barra
_MARKER_R    = 3.5  # raggio cerchio marker
_PAD_X       = 4    # padding laterale


class Gauge(QWidget):
    """
    Gauge orizzontale con zone semantiche e marker di posizione.

    Parametri:
        width, height  dimensioni fisse (default 140x28)
        zones          lista di (min, max, color_hex) — default = Hurst
        label          etichetta in alto a sinistra (uppercase automatico)

    API:
        set_value(v)        valore 0.0–1.0 (clampato automaticamente)
        set_label(s)        aggiorna etichetta
        set_zones(zones)    sostituisce le zone colorate

    Uso:
        g = Gauge(label="HURST")
        g.set_value(0.63)

        g2 = Gauge(
            label="KELLY",
            zones=[(0, 0.25, "#f85149"), (0.25, 0.75, "#d29922"), (0.75, 1, "#3fb950")]
        )
        g2.set_value(0.40)
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 140,
        height: int = 28,
        zones: list[tuple[float, float, str]] | None = None,
        label: str = "",
    ) -> None:
        super().__init__(parent)
        self._w = width
        self._h = height
        self._zones: list[tuple[float, float, str]] = (
            list(zones) if zones is not None else list(_DEFAULT_ZONES)
        )
        self._label = label
        self._value: float = 0.0

        self.setFixedSize(width, height)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._refresh_tooltip()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_value(self, value: float) -> None:
        """Imposta il valore 0-1. Clamp automatico."""
        self._value = max(0.0, min(1.0, float(value)))
        self._refresh_tooltip()
        self.update()

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    def set_zones(self, zones: list[tuple[float, float, str]]) -> None:
        self._zones = list(zones)
        self._refresh_tooltip()
        self.update()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _refresh_tooltip(self) -> None:
        zone = self._zone_label(self._value)
        lbl  = self._label or "VALUE"
        self.setToolTip(f"{lbl}  {self._value:.3f}  [{zone}]")

    def _zone_label(self, v: float) -> str:
        """Restituisce il nome leggibile della zona per il valore dato."""
        for zmin, zmax, color in self._zones:
            if zmin <= v <= zmax:
                # Mappa colore → nome semantico (per zone Hurst default)
                mapping = {_BULL: "trending", _BEAR: "mean-rev", _WARN: "random"}
                return mapping.get(color, "zone")
        return "—"

    def _active_color(self) -> QColor:
        """Colore della zona in cui cade il valore corrente."""
        for zmin, zmax, color in self._zones:
            if zmin <= self._value <= zmax:
                return QColor(color)
        return QColor(_MUTED)

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
        f.setPixelSize(9)
        f.setWeight(QFont.Weight.DemiBold)
        return f

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = float(self._w)
        h = float(self._h)

        # Layout verticale:
        #   [0 .. LABEL_H]                    testo label + valore
        #   [LABEL_H + PAD_BETWEEN .. +TRACK_H]  barra
        track_top = float(_LABEL_H + _PAD_BETWEEN)
        track_bot = track_top + float(_TRACK_H)
        tx1 = float(_PAD_X)
        tx2 = w - float(_PAD_X)
        tw  = tx2 - tx1   # larghezza usabile del track

        # ── Riga 1: label (sx) + valore numerico (dx) ────────────────────
        label_rect = QRectF(tx1, 0.0, tw * 0.55, float(_LABEL_H))
        val_rect   = QRectF(tx1 + tw * 0.45, 0.0, tw * 0.55, float(_LABEL_H))

        if self._label:
            painter.setFont(self._font_label())
            painter.setPen(QColor(_MUTED))
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self._label.upper(),
            )

        active_col = self._active_color()
        painter.setFont(self._font_value())
        painter.setPen(active_col)
        painter.drawText(
            val_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{self._value:.3f}",
        )

        # ── Track: sfondo pill ────────────────────────────────────────────
        track_rect = QRectF(tx1, track_top, tw, float(_TRACK_H))
        r = float(_TRACK_H) / 2.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_TRACK_BG))
        painter.drawRoundedRect(track_rect, r, r)

        # ── Zone colorate (clippate alla forma pill) ──────────────────────
        clip = QPainterPath()
        clip.addRoundedRect(track_rect, r, r)
        painter.setClipPath(clip)

        for zmin, zmax, color_hex in self._zones:
            zx1 = tx1 + zmin * tw
            zx2 = tx1 + zmax * tw
            zrect = QRectF(zx1, track_top, zx2 - zx1, float(_TRACK_H))
            zc = QColor(color_hex)
            zc.setAlpha(55)
            painter.setBrush(zc)
            painter.drawRect(zrect)

        # ── Fill dal bordo sx fino al valore (colore zona, opaco) ─────────
        fill_w = self._value * tw
        if fill_w > 0.5:
            fill_col = QColor(active_col)
            fill_col.setAlpha(190)
            painter.setBrush(fill_col)
            painter.drawRect(QRectF(tx1, track_top, fill_w, float(_TRACK_H)))

        painter.setClipping(False)

        # ── Marker: linea verticale + cerchio ──────────────────────────────
        mx = tx1 + self._value * tw
        cy = track_top + float(_TRACK_H) / 2.0

        # Linea verticale da sopra il track fino a sotto (col glow opzionale)
        painter.setPen(QPen(active_col, 1.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(
            QPointF(mx, track_top - 2.5),
            QPointF(mx, track_bot + 1.0),
        )

        # Alone (halo) per il cerchio
        halo = QColor(active_col)
        halo.setAlpha(35)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(QPointF(mx, cy), _MARKER_R + 2.5, _MARKER_R + 2.5)

        # Cerchio pieno con bordo scuro sottile
        painter.setPen(QPen(QColor("#0d1117"), 1.0))
        painter.setBrush(active_col)
        painter.drawEllipse(QPointF(mx, cy), _MARKER_R, _MARKER_R)

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._w, self._h)
