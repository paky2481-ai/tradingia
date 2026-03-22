"""
TradingIA GUI Application Entry Point v2

Avvia la GUI e, opzionalmente, il motore automatico in background.
L'engine e la GUI condividono lo stesso asyncio event loop (qasync).

Uso:
    python main.py gui                    # GUI senza engine
    python main.py gui --autorun          # GUI + engine automatico (paper)
    python main.py gui --autorun --live   # GUI + engine live
"""

from __future__ import annotations

import asyncio
import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
import qasync

from gui.styles import load_stylesheet
from gui.main_window import TradingMainWindow


def run(autorun: bool = False, capital: float = 1000.0, mode: str = "paper"):
    """Lancia l'applicazione desktop."""
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("TradingIA")
    app.setOrganizationName("TradingIA")
    app.setApplicationVersion("2.0.0")

    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    app.setFont(font)

    app.setStyleSheet(load_stylesheet())

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = TradingMainWindow()
    window.show()

    with loop:
        async def _start():
            # Init DB
            try:
                from database.db import init_db
                await init_db()
            except Exception as e:
                print(f"[WARN] DB init: {e}")

            # Avvia engine se richiesto
            if autorun:
                from core.engine import TradingEngine
                engine = TradingEngine(capital=capital, mode=mode)
                window.set_engine(engine)
                # Avvia in background (il loop gestisce tutto)
                asyncio.ensure_future(engine.run())

        loop.run_until_complete(_start())
        loop.run_forever()
