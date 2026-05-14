"""
gui/workspaces — workspace modulari Bloomberg-style.

Ogni workspace è un QWidget autonomo che Paky inserisce nel QStackedWidget
della shell principale. Ogni workspace accede ad AppState ma non conosce
la MainWindow.

Workspace disponibili:
    DashboardWorkspace  — overview globale con watchlist, chart, AI panel (MVP)
"""

from .dashboard import DashboardWorkspace

__all__ = ["DashboardWorkspace"]
