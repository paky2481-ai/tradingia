"""
analysis.py — redirect di retrocompatibilità.

Il workspace di analisi è stato sostituito dall'AIObservatoryWorkspace (A.3).
Questo modulo esporta AIObservatoryWorkspace come AnalysisWorkspace per
non rompere eventuali import legacy.

Il file verrà rimosso in una fase futura (vedi data_panel.py).
"""
from __future__ import annotations

# Redirect: usa il nuovo AIObservatoryWorkspace
from gui.workspaces.ai_observatory import AIObservatoryWorkspace as AnalysisWorkspace  # noqa: F401

__all__ = ["AnalysisWorkspace"]
