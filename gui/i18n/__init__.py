"""
[Paky] gui/i18n — Infrastruttura internazionalizzazione TradingIA

Uso tipico:
    from gui.i18n import tr, set_language, current_language

    tr("topbar.equity")                    # -> "CAPITALE" (IT default)
    tr("broker.connected", ms=23)          # -> "Connesso · 23ms"
    set_language("en")
    tr("topbar.equity")                    # -> "EQUITY"
"""

from gui.i18n.strings import tr, set_language, current_language

__all__ = ["tr", "set_language", "current_language"]
