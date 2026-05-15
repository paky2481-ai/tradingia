"""
KPIBadge — badge compatto Bloomberg-grade con label + valore + delta + sparkline.

Design:
  - Struttura verticale: label (9px uppercase muted) / value (13px mono bold)
  - Delta affianco al valore, colorato bull/bear, prefisso segno esplicito
  - Sparkline opzionale a sinistra, allineata verticalmente al centro
  - Padding 4px, niente bordi, sfondo trasparente: si integra in qualsiasi TopBar/panel
  - sizeHint preciso per evitare collasso layout in widget contenitori densi
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, QEvent
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget, QToolTip,
)

from .sparkline import Sparkline


# ── Palette (stringhe per QSS inline) ────────────────────────────────────────
_TEXT   = "#e6edf3"
_MUTED  = "#8b949e"
_BULL   = "#3fb950"
_BEAR   = "#f85149"
_WARN   = "#d29922"
_ACCENT = "#a371f7"

# Font stack usato per tutti i QLabel numerici
_MONO_STACK = '"Consolas", "Cascadia Code", "JetBrains Mono", monospace'
_UI_STACK   = '"Segoe UI", "Inter", "SF Pro Display", sans-serif'


def _qlabel(
    text: str = "",
    size: int = 12,
    color: str = _TEXT,
    bold: bool = False,
    mono: bool = False,
    uppercase: bool = False,
) -> QLabel:
    """Factory QLabel con stile inline completo."""
    lbl = QLabel(text)
    family = _MONO_STACK if mono else _UI_STACK
    weight = "700" if bold else "400"
    xform  = "uppercase" if uppercase else "none"
    lbl.setStyleSheet(
        f"color:{color}; font-size:{size}px; font-weight:{weight};"
        f" font-family:{family}; text-transform:{xform};"
        f" background:transparent; letter-spacing:0.3px; border:none;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return lbl


class KPIBadge(QWidget):
    """
    Badge compatto per TopBar o panel info.

    Layout (orizzontale):
        [Sparkline?] | LABEL (9px muted uppercase)
                       VALUE  (13px mono bold)  +delta (10px mono bull/bear)

    Uso:
        badge = KPIBadge("PnL", show_sparkline=True)
        badge.set_value("+1,234.56")
        badge.set_delta(+2.34, "%")
        badge.set_sparkline_values([100, 102, 99, 105, 103])
    """

    def __init__(
        self,
        label: str,
        parent: QWidget | None = None,
        value_color: str = _TEXT,
        monospace: bool = True,
        show_sparkline: bool = False,
        sparkline_width: int = 60,
        sparkline_height: int = 22,
    ) -> None:
        super().__init__(parent)
        self._value_color = value_color
        self._monospace = monospace

        # Sfondo trasparente per integrarsi nella topbar
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setContentsMargins(4, 2, 4, 2)

        # ── Layout principale (orizzontale) ───────────────────────────────
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(7)

        # Sparkline opzionale, allineata verticalmente
        self._sparkline: Sparkline | None = None
        if show_sparkline:
            self._sparkline = Sparkline(
                width=sparkline_width,
                height=sparkline_height,
            )
            outer.addWidget(self._sparkline, 0, Qt.AlignmentFlag.AlignVCenter)

        # ── Colonna testo ─────────────────────────────────────────────────
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)

        # Riga 1: etichetta
        self._lbl_label = _qlabel(
            label.upper(), size=9, color=_MUTED, uppercase=True
        )
        col.addWidget(self._lbl_label)

        # Riga 2: valore + delta inline
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(4)

        self._lbl_value = _qlabel(
            "—", size=13, color=value_color, bold=True, mono=monospace
        )
        row2.addWidget(self._lbl_value, 0, Qt.AlignmentFlag.AlignVCenter)

        self._lbl_delta = _qlabel("", size=10, color=_MUTED, mono=True)
        self._lbl_delta.setVisible(False)
        row2.addWidget(self._lbl_delta, 0, Qt.AlignmentFlag.AlignVCenter)
        row2.addStretch(1)

        col.addLayout(row2)
        outer.addLayout(col)
        outer.addStretch(0)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_value(self, value: str) -> None:
        """Imposta il testo del valore principale. Accetta qualsiasi stringa formattata."""
        self._lbl_value.setText(value)

    def set_delta(self, delta: float, unit: str = "%") -> None:
        """
        Mostra il delta colorato. Segno esplicito (+/-/±). Zero = muted.
        delta=+2.34, unit="%" → "+2.34%"  (verde)
        delta=-0.51, unit="%" → "-0.51%"  (rosso)
        """
        if delta == 0:
            sign, color = "±", _MUTED
        elif delta > 0:
            sign, color = "+", _BULL
        else:
            sign, color = "", _BEAR   # il segno - e' gia' nel numero

        # Formattazione: 2 decimali se |delta| < 1000, altrimenti 0
        if abs(delta) < 100:
            fmt = f"{delta:.2f}"
        elif abs(delta) < 10000:
            fmt = f"{delta:.1f}"
        else:
            fmt = f"{delta:.0f}"

        self._lbl_delta.setText(f"{sign}{fmt}{unit}")
        self._lbl_delta.setStyleSheet(
            f"color:{color}; font-size:10px; font-weight:500;"
            f" font-family:{_MONO_STACK};"
            f" background:transparent; border:none;"
        )
        self._lbl_delta.setVisible(True)

    def hide_delta(self) -> None:
        """Nasconde la sezione delta (es. quando dato non disponibile)."""
        self._lbl_delta.setVisible(False)

    def set_sparkline_values(self, values: list[float]) -> None:
        """Aggiorna la sparkline se presente. Silenzioso se non abilitata."""
        if self._sparkline is not None:
            self._sparkline.set_values(values)

    def set_label_text(self, label: str) -> None:
        self._lbl_label.setText(label.upper())

    def set_value_color(self, color: str) -> None:
        """Cambia il colore del valore runtime (es. per flash bull/bear)."""
        self._lbl_value.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:700;"
            f" font-family:{_MONO_STACK};"
            f" background:transparent; letter-spacing:0.3px; border:none;"
        )

    def sizeHint(self) -> QSize:
        # Calcolo preciso per evitare collasso in layout densi
        text_w = 80  # valore approssimativo sicuro
        text_h = 9 + 1 + 14  # label + spacing + value
        sl_w = self._sparkline.width() + 7 if self._sparkline else 0
        return QSize(sl_w + text_w + 8, text_h + 4)

    def event(self, e: QEvent) -> bool:
        """Ancora il tooltip al bordo inferiore-sinistro del widget (non al cursore)."""
        if e.type() == QEvent.Type.ToolTip:
            if self.toolTip():
                pos = self.mapToGlobal(self.rect().bottomLeft())
                QToolTip.showText(pos, self.toolTip(), self)
                return True
        return super().event(e)
