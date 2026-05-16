"""
LiveLabel — QLabel con flash 100ms su update (per prezzi live).

Design:
  - Sottoclasse di QLabel
  - Quando set_value() viene chiamato, il background diventa flash_color
    per ~100ms poi torna trasparente con fade via QTimer
  - Font monospace 12px (Consolas/Cascadia)
  - Nessun tooltip default (il chiamante imposta tooltip esterno)
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QWidget


class LiveLabel(QLabel):
    """
    QLabel con flash visivo al cambio valore (prezzi live).

    API (estende QLabel):
        set_value(value: str)              set text + scatena flash
        set_flash_color(color: str)        colore del flash background (default #1f6feb)

    Uso:
        lbl = LiveLabel("---.--")
        lbl.set_flash_color("#3fb950")  # verde per valori positivi
        lbl.set_value("1.2345")
    """

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._flash_color: str = "#1f6feb"
        self._base_style: str = (
            "font-family: Consolas, 'Cascadia Code', 'JetBrains Mono', monospace;"
            "font-size: 12px;"
            "color: #e6edf3;"
            "padding: 0 2px;"
            "background: transparent;"
        )
        self.setStyleSheet(self._base_style)

        # Timer per rimettere il background trasparente
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._clear_flash)

    # ── API pubblica ──────────────────────────────────────────────────────────

    def set_value(self, value: str) -> None:
        """Aggiorna il testo e scatena il flash."""
        self.setText(value)
        self._start_flash()

    def set_flash_color(self, color: str = "#1f6feb") -> None:
        """Imposta il colore del flash background."""
        self._flash_color = color

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _start_flash(self) -> None:
        """Applica il colore flash e avvia il timer di decadimento."""
        flash_style = (
            "font-family: Consolas, 'Cascadia Code', 'JetBrains Mono', monospace;"
            f"font-size: 12px;"
            "color: #e6edf3;"
            "padding: 0 2px;"
            f"background: {self._flash_color}22;"  # alpha basso (8%)
            "border-radius: 2px;"
        )
        self.setStyleSheet(flash_style)
        self._timer.start()

    def _clear_flash(self) -> None:
        """Rimuove il flash e ripristina il background trasparente."""
        self.setStyleSheet(self._base_style)
