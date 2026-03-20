"""
TradingIA GUI Application Entry Point
Boots the Qt application with qasync event loop so async backend code
(data feeds, AI models) runs seamlessly inside the Qt main thread.
"""

from __future__ import annotations

import asyncio
import sys
import os

# Qt must be imported before pyqtgraph
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
import qasync

from gui.styles import load_stylesheet
from gui.main_window import TradingMainWindow


def run():
    """Launch the desktop application."""
    # High-DPI support (Qt6 default, but explicit for clarity)
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("TradingIA")
    app.setOrganizationName("TradingIA")
    app.setApplicationVersion("1.0.0")

    # Global font
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(font)

    # Dark stylesheet
    app.setStyleSheet(load_stylesheet())

    # qasync: merge asyncio event loop with Qt event loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = TradingMainWindow()
    window.show()

    with loop:
        loop.run_forever()
