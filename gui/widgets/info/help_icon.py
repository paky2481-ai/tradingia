"""
HelpIcon — cerchio "?" muted cliccabile con tooltip + MessageBox esplicativa.

Design:
  - Cerchio 16x16px, sfondo #21262d, testo "#a8b1bb", bordo-radius 8px
  - Hover: sfondo #1f6feb (blu accent), testo bianco
  - Tooltip nativo HTML (multilinea, max ~400 char)
  - Click: QMessageBox con titolo bold + corpo esteso + bottone Chiudi
  - Cursore: PointingHand per affordance immediata
  - Zero dipendenze esterne oltre PyQt6
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMessageBox


class HelpIcon(QLabel):
    """
    Cerchio "?" riutilizzabile per spiegare metriche a utenti non tecnici.

    Uso:
        icon = HelpIcon(
            title="Hurst Exponent",
            body="Misura la persistenza del trend. Sopra 0.6 = trend forte.",
        )
        layout.addWidget(icon)

    Il tooltip appare al hover. Il click apre una QMessageBox con il testo completo.
    """

    def __init__(self, title: str, body: str, parent: QLabel | None = None) -> None:
        """
        Args:
            title: titolo breve (es. "Hurst Exponent") — usato come intestazione
            body:  spiegazione lunga in italiano semplice — testo aiuto esteso
        """
        super().__init__(parent)
        self._title = title
        self._body = body

        self.setText("?")
        self.setFixedSize(16, 16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QLabel {"
            "  background: #21262d;"
            "  color: #a8b1bb;"
            "  border-radius: 8px;"
            "  font-size: 10px;"
            "  font-weight: bold;"
            '  font-family: "Segoe UI", "Inter", sans-serif;'
            "}"
            "QLabel:hover {"
            "  background: #1f6feb;"
            "  color: white;"
            "}"
        )
        # Tooltip HTML nativo — visibile già al hover, max ~400 char per leggibilità
        self.setToolTip(f"<b>{title}</b><br>{body}")

    # ── Event ──────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Su click sinistro apre MessageBox con spiegazione estesa."""
        if event.button() == Qt.MouseButton.LeftButton:
            box = QMessageBox(self)
            box.setWindowTitle(self._title)
            box.setText(f"<b>{self._title}</b>")
            box.setInformativeText(self._body)
            box.setStandardButtons(QMessageBox.StandardButton.Close)
            # Stile coerente con il dark theme dell'app
            box.setStyleSheet(
                "QMessageBox {"
                "  background-color: #161b22;"
                "  color: #e6edf3;"
                "}"
                "QMessageBox QLabel {"
                "  color: #e6edf3;"
                "  font-size: 13px;"
                "  background: transparent;"
                "}"
                "QPushButton {"
                "  background-color: #21262d;"
                "  color: #e6edf3;"
                "  border: 1px solid #30363d;"
                "  border-radius: 6px;"
                "  padding: 4px 16px;"
                "  font-size: 12px;"
                "}"
                "QPushButton:hover {"
                "  background-color: #1f6feb;"
                "  border-color: #1f6feb;"
                "}"
            )
            box.exec()
        else:
            super().mousePressEvent(event)
