"""
gui/widgets/info — Libreria micro-componenti per trading UI Bloomberg-grade.

MVP (fase 1):
    Sparkline        — mini chart a linea, 80x24px
    KPIBadge         — label + valore + delta + sparkline opzionale
    RegimePill       — pill colorato regime di mercato
    Gauge            — barra orizzontale 0-1 con zone semantiche
    HelpIcon         — cerchio "?" cliccabile con tooltip + MessageBox

Fase 4 (8 nuovi):
    ConfidenceBar    — barra orizzontale 0-1 con threshold marker
    BiDirectionalBar — barra bull/bear split dal centro
    Heatmap          — matrice correlazioni N×N colorata
    PingIndicator    — dot + latency ms + uptime%
    StatusDot        — LED idle/active/error/loading con animazione
    LiveLabel        — QLabel con flash 100ms su update prezzi live
    FFTMini          — spettro frequenze 120x40 con peak marker
    NumericTable     — QTableWidget monospace Bloomberg-grade + sparkline

Uso:
    from gui.widgets.info import (
        Sparkline, KPIBadge, RegimePill, Gauge, HelpIcon,
        ConfidenceBar, BiDirectionalBar, Heatmap, PingIndicator,
        StatusDot, LiveLabel, FFTMini, NumericTable,
    )
"""

from .sparkline import Sparkline
from .kpi_badge import KPIBadge
from .regime_pill import RegimePill
from .gauge import Gauge
from .help_icon import HelpIcon
from .confidence_bar import ConfidenceBar
from .bidir_bar import BiDirectionalBar
from .heatmap import Heatmap
from .ping_indicator import PingIndicator
from .status_dot import StatusDot
from .live_label import LiveLabel
from .fft_mini import FFTMini
from .numeric_table import NumericTable

__all__ = [
    # fase 1
    "Sparkline",
    "KPIBadge",
    "RegimePill",
    "Gauge",
    "HelpIcon",
    # fase 4
    "ConfidenceBar",
    "BiDirectionalBar",
    "Heatmap",
    "PingIndicator",
    "StatusDot",
    "LiveLabel",
    "FFTMini",
    "NumericTable",
]
