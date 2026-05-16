"""
StatusDot — LED indicatore di stato per loop async.

Design:
  - Dot 12x12 px con colore semantico e leggero glow per active/error
  - Etichetta opzionale a destra
  - Stato "loading": pulsazione blu via QTimer (alpha oscillante)
  - Tutto il rendering via QPainter custom
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget


# ── Palette ───────────────────────────────────────────────────────────────────
_IDLE    = QColor("#6e7681")
_ACTIVE  = QColor("#3fb950")
_ERROR   = QColor("#f85149")
_LOADING = QColor("#58a6ff")

_STATE_COLORS: dict[str, QColor] = {
    "idle":    _IDLE,
    "active":  _ACTIVE,
    "error":   _ERROR,
    "loading": _LOADING,
}

# Dot geometry
_DOT_D = 8   # diametro dot effettivo
_PAD   = 2   # padding attorno al dot per il glow


class _DotCanvas(QWidget):
    """Solo il cerchio colorato — 12x12 px."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: str = "idle"
        self._pulse_alpha: int = 255

        self.setFixedSize(12, 12)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        # Timer pulsazione per stato loading
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick_pulse)
        self._pulse_dir: int = -10

    # ── API ──────────────────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "loading":
            self._pulse_alpha = 255
            self._timer.start()
        else:
            self._timer.stop()
            self._pulse_alpha = 255
        self.update()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _tick_pulse(self) -> None:
        self._pulse_alpha += self._pulse_dir * 12
        if self._pulse_alpha <= 80:
            self._pulse_alpha = 80
            self._pulse_dir = 10
        elif self._pulse_alpha >= 255:
            self._pulse_alpha = 255
            self._pulse_dir = -10
        self.update()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(_STATE_COLORS.get(self._state, _IDLE))

        cx = 6.0
        cy = 6.0
        r  = _DOT_D / 2.0

        # Glow per active/error/loading
        if self._state in ("active", "error", "loading"):
            glow = QColor(color)
            glow.setAlpha(40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(QPointF(cx, cy), r + 3.0, r + 3.0)

        # Dot principale
        if self._state == "loading":
            color.setAlpha(self._pulse_alpha)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        painter.end()


class StatusDot(QWidget):
    """
    LED indicatore di stato per loop async.

    Stati accettati: "idle", "active", "error", "loading"

    API:
        set_state(state)   aggiorna il colore/animazione
        set_label(text)    etichetta opzionale a destra del dot
        pulse()            flash 100ms (per heartbeat)

    Uso:
        dot = StatusDot()
        dot.set_state("active")
        dot.set_label("Engine")
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dot = _DotCanvas(self)
        self._label_text: str = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._dot)
        layout.addStretch()

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(14)

        # Timer per pulse flash
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._end_pulse)
        self._pre_pulse_state: str = "idle"

        self._update_tooltip()

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        """Imposta lo stato: idle | active | error | loading."""
        self._dot.set_state(state)
        self._update_tooltip()
        self.update()

    def set_label(self, text: str) -> None:
        """Etichetta opzionale a destra del dot."""
        self._label_text = text
        # Aggiustiamo larghezza minima in base al testo
        self.setMinimumWidth(12 + 4 + max(0, len(text) * 7))
        self.update()

    def pulse(self) -> None:
        """Flash 100ms per heartbeat visivo."""
        self._pre_pulse_state = self._dot._state
        self._dot.set_state("active")
        self._flash_timer.start(100)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _end_pulse(self) -> None:
        self._dot.set_state(self._pre_pulse_state)

    def _update_tooltip(self) -> None:
        labels = {
            "idle":    "Status: Idle",
            "active":  "Status: Active",
            "error":   "Status: Error",
            "loading": "Status: Loading",
        }
        self.setToolTip(labels.get(self._dot._state, "Status: Unknown"))

    # ── Rendering (solo label testo se presente) ──────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        if not self._label_text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        from PyQt6.QtGui import QFont
        f = QFont()
        f.setFamilies(["Segoe UI", "Inter", "sans-serif"])
        f.setPixelSize(10)
        painter.setFont(f)
        painter.setPen(QColor("#a8b1bb"))

        # Testo a destra del dot (dot=12px + spacing=4px)
        text_rect = QRectF(16.0, 0.0, float(self.width() - 16), float(self.height()))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._label_text,
        )
        painter.end()

    def sizeHint(self) -> QSize:
        base_w = 12
        if self._label_text:
            base_w += 4 + len(self._label_text) * 7
        return QSize(base_w, 14)
