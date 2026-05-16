"""
RegimePill — pill arrotondato che mostra regime di mercato + Hurst exponent.

Design:
  - Pill con border-radius 11px (metà altezza 22px)
  - Sfondo colorato semantico: verde/grigio/blu/scuro per trending/choppy/cycling/unknown
  - Bordo sottile 1px dello stesso colore ma piu' luminoso
  - Simbolo ASCII-safe + label uppercase + valore Hurst opzionale
  - Font 10px DemiBold, lettering +0.5px per leggibilita'
  - Larghezza auto-fit calcolata su QFontMetrics, altezza fissa 22px
  - Tooltip descrittivo con significato del regime
"""
from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

from gui.i18n import tr


# ── Configurazione regimi ─────────────────────────────────────────────────────
# Simboli ASCII-safe per evitare buchi con font privi di glifi Unicode rari.
# "~" per choppy e "~" per cycling e' intenzionale: su trading terminal
# il simbolo universale di rumore e' "~".
# label e tooltip sono caricati dinamicamente via tr() al momento del render
# per supportare cambio lingua runtime.
_REGIMES: dict[str, dict] = {
    "trending": {
        "symbol": "^",
        "bg":     QColor(13, 51, 32),     # verde molto scuro  #0d3320
        "border": QColor(46, 160, 67),    # #2ea043
        "text":   QColor(63, 185, 80),    # #3fb950 BULL
    },
    "choppy": {
        "symbol": "~",
        "bg":     QColor(28, 29, 33),     # grigio neutro scuro
        "border": QColor(72, 79, 88),     # #484f58
        "text":   QColor(139, 148, 158),  # #8b949e MUTED
    },
    "cycling": {
        "symbol": "o",
        "bg":     QColor(10, 22, 40),     # blu scuro #0a1628
        "border": QColor(31, 111, 235),   # #1f6feb
        "text":   QColor(88, 166, 255),   # #58a6ff INFO light
    },
    "unknown": {
        "symbol": "?",
        "bg":     QColor(22, 27, 34),     # #161b22 BG_SURFACE
        "border": QColor(48, 54, 61),     # #30363d BORDER
        "text":   QColor(72, 79, 88),     # #484f58 TEXT_DIM
    },
}


def _regime_label(regime: str) -> str:
    """Ritorna la label tradotta per il regime (es. 'IN TREND' in IT, 'TRENDING' in EN)."""
    return tr(f"regime.{regime}")


def _regime_tooltip(regime: str) -> str:
    """Ritorna il tooltip tradotto per il regime."""
    return tr(f"regime.tooltip.{regime}")

_PILL_H  = 22   # altezza fissa pill
_RADIUS  = 11   # border-radius = altezza/2 per pill perfetto
_PAD_H   = 10   # padding orizzontale interno


class RegimePill(QWidget):
    """
    Pill colorato che indica il regime di mercato attivo.

    Uso:
        pill = RegimePill()
        pill.set_regime("trending", 0.62)
        pill.set_regime("choppy", 0.47)
        pill.set_regime("unknown")       # nessun Hurst
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._regime = "unknown"
        self._hurst: float | None = None
        self._text = "? UNKNOWN"

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedHeight(_PILL_H)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._recalc()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_regime(self, regime: str, hurst: float | None = None) -> None:
        """
        Imposta il regime. hurst e' opzionale.
        Se hurst e' None, il label non mostra il valore numerico.
        """
        self._regime = regime if regime in _REGIMES else "unknown"
        self._hurst = hurst
        self._recalc()
        self.update()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _build_font(self) -> QFont:
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "SF Pro Display", "sans-serif"])
        f.setPixelSize(10)
        f.setWeight(QFont.Weight.DemiBold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        return f

    def _recalc(self) -> None:
        """Ricalcola il testo e la larghezza auto-fit."""
        cfg = _REGIMES[self._regime]
        sym  = cfg["symbol"]
        lbl  = _regime_label(self._regime)

        if self._hurst is not None:
            self._text = f"{sym} {lbl}  H {self._hurst:.2f}"
        else:
            self._text = f"{sym} {lbl}"

        font = self._build_font()
        fm   = QFontMetrics(font)
        text_w = fm.horizontalAdvance(self._text)
        self.setFixedWidth(max(text_w + _PAD_H * 2, 88))

        tip = _regime_tooltip(self._regime)
        if self._hurst is not None:
            tip = f"H={self._hurst:.3f}  —  {tip}"
        self.setToolTip(tip)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        cfg = _REGIMES[self._regime]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # Rect con 0.5px inset per bordo netto (anti-aliasing border)
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)

        # ── Sfondo pill ───────────────────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(rect, _RADIUS, _RADIUS)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(cfg["bg"])
        painter.drawPath(path)

        # ── Bordo 1px ─────────────────────────────────────────────────────
        painter.setPen(QPen(cfg["border"], 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # ── Testo centrato ────────────────────────────────────────────────
        painter.setFont(self._build_font())
        painter.setPen(cfg["text"])
        painter.drawText(
            QRectF(0.0, 0.0, float(w), float(h)),
            Qt.AlignmentFlag.AlignCenter,
            self._text,
        )

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self.width(), _PILL_H)
