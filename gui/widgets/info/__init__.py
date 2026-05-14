"""
gui/widgets/info — Libreria micro-componenti per trading UI Bloomberg-grade.

MVP (fase 1):
    Sparkline      — mini chart a linea, 80x24px
    KPIBadge       — label + valore + delta + sparkline opzionale
    RegimePill     — pill colorato regime di mercato
    Gauge          — barra orizzontale 0-1 con zone semantiche
    HelpIcon       — cerchio "?" cliccabile con tooltip + MessageBox

Uso:
    from gui.widgets.info import Sparkline, KPIBadge, RegimePill, Gauge, HelpIcon
"""

from .sparkline import Sparkline
from .kpi_badge import KPIBadge
from .regime_pill import RegimePill
from .gauge import Gauge
from .help_icon import HelpIcon

__all__ = [
    "Sparkline",
    "KPIBadge",
    "RegimePill",
    "Gauge",
    "HelpIcon",
]
