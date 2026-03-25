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

# Pre-load torch BEFORE PyQt6 — evita conflitti DLL su Windows (c10.dll)
try:
    import torch  # noqa: F401
except Exception:
    pass

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
import qasync


def _qt_message_handler(msg_type, context, message):
    """Sopprime il warning pyqtgraph/Qt6 sui font con pointSize=-1."""
    if "setPointSize" in message and "Point size <= 0" in message:
        return
    # Tutti gli altri messaggi: comportamento default (stampa su stderr)
    if msg_type == QtMsgType.QtFatalMsg:
        raise RuntimeError(message)

from gui.styles import load_stylesheet
from gui.main_window import TradingMainWindow


def run(autorun: bool = False, capital: float = 1000.0, mode: str = "paper"):
    """Lancia l'applicazione desktop."""
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    qInstallMessageHandler(_qt_message_handler)

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

            # Avvia TestServer per testing autonomo (127.0.0.1:7779)
            try:
                from core.test_server import test_server
                await test_server.start()
                from utils.logger import attach_test_server_sink
                attach_test_server_sink()
            except Exception as e:
                print(f"[WARN] TestServer non avviato: {e}")

            # Avvia engine se richiesto
            if autorun:
                from core.engine import TradingEngine
                engine = TradingEngine(capital=capital, mode=mode)
                window.set_engine(engine)
                asyncio.ensure_future(engine.run())

        loop.run_until_complete(_start())
        loop.run_forever()
