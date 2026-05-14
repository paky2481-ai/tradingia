"""
gui/styles — Gestione stylesheet TradingIA.

Hierarchy:
    dark.qss          stylesheet principale (Bloomberg-grade, completo)
    dark_theme.qss    stylesheet legacy (mantenuto per compatibilita')

load_stylesheet() carica dark.qss e restituisce la stringa CSS.
Se dark.qss non esiste (sviluppo) fa fallback su dark_theme.qss.
"""
import os

_DIR = os.path.dirname(__file__)


def load_stylesheet() -> str:
    """
    Carica e restituisce il contenuto del foglio di stile dark premium.

    Priorita':
        1. dark.qss        — nuovo stylesheet Bloomberg-grade
        2. dark_theme.qss  — fallback legacy

    Uso:
        from gui.styles import load_stylesheet
        app.setStyleSheet(load_stylesheet())
    """
    primary  = os.path.join(_DIR, "dark.qss")
    fallback = os.path.join(_DIR, "dark_theme.qss")

    for path in (primary, fallback):
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()

    # Nessun file trovato: stringa vuota, Qt usa il default
    return ""
