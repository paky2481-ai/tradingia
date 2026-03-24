"""
Pannello Backtest — TradingIA GUI
Permette di configurare ed eseguire un backtest visualmente,
mostrando equity curve, metriche e log dei trade in tempo reale.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from PyQt6 import uic
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QGroupBox, QLineEdit, QFrame,
)
from PyQt6.QtGui import QColor, QFont

_UI = Path(__file__).parent.parent / "ui" / "backtest_panel.ui"

try:
    import pyqtgraph as pg
    _PG_OK = True
except ImportError:
    _PG_OK = False

from backtesting.backtester import Backtester, BacktestResult
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="gui.backtest_panel")

_STRATEGIES = [
    "trend_following",
    "mean_reversion",
    "breakout",
    "scalping",
    "ai_ensemble",
]

_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]

_METRIC_STYLE_BASE = (
    "background:#161b22; border:1px solid #30363d; border-radius:6px; padding:6px 10px;"
)

# ─────────────────────────────────────────────────────────────────────────────
# Worker (QThread) — esegue il backtest in background
# ─────────────────────────────────────────────────────────────────────────────

class _BacktestWorker(QObject):
    """Esegue Backtester.run() in un QThread separato."""

    progress = pyqtSignal(int)               # 0-100
    finished = pyqtSignal(object)            # BacktestResult
    error    = pyqtSignal(str)

    def __init__(self, symbol: str, strategy_name: str, timeframe: str,
                 capital: float, window_days: int):
        super().__init__()
        self.symbol        = symbol
        self.strategy_name = strategy_name
        self.timeframe     = timeframe
        self.capital       = capital
        self.window_days   = window_days

    @pyqtSlot()
    def run(self):
        try:
            # ── Fetch dati (sincrono — siamo in QThread) ──────────────────
            from data.feed import UniversalDataFeed
            feed = UniversalDataFeed()
            loop = asyncio.new_event_loop()

            # Calcola il limit in barre dal window_days
            hours_per_bar = {"1m": 1/60, "5m": 1/12, "15m": 1/4, "30m": 1/2,
                             "1h": 1, "4h": 4, "1d": 24}
            h = hours_per_bar.get(self.timeframe, 1)
            limit = max(300, int(self.window_days * 24 / h))

            df: Optional[pd.DataFrame] = loop.run_until_complete(
                feed.get_ohlcv(self.symbol, self.timeframe, limit=limit)
            )
            loop.run_until_complete(feed.close())
            loop.close()

            if df is None or df.empty:
                self.error.emit(f"Nessun dato disponibile per {self.symbol} [{self.timeframe}]")
                return

            # ── Crea strategia ────────────────────────────────────────────
            strategy = _build_strategy(self.strategy_name, self.timeframe)
            if strategy is None:
                self.error.emit(f"Strategia '{self.strategy_name}' non trovata")
                return

            # ── Esegui backtest con progress ──────────────────────────────
            bt = Backtester(initial_capital=self.capital)
            result = bt.run(
                df, strategy, self.symbol,
                progress_callback=lambda p: self.progress.emit(p),
            )
            self.finished.emit(result)

        except Exception as e:
            logger.error(f"BacktestWorker error: {e}", exc_info=True)
            self.error.emit(str(e))


def _build_strategy(name: str, timeframe: str):
    """Istanzia la strategia per nome."""
    try:
        from strategies.technical_strategy import (
            TrendFollowingStrategy, MeanReversionStrategy,
            BreakoutStrategy, ScalpingStrategy,
        )
        from strategies.ai_strategy import AIStrategy

        mapping = {
            "trend_following": TrendFollowingStrategy,
            "mean_reversion":  MeanReversionStrategy,
            "breakout":        BreakoutStrategy,
            "scalping":        ScalpingStrategy,
            "ai_ensemble":     AIStrategy,
        }
        cls = mapping.get(name)
        return cls(timeframe=timeframe) if cls else None
    except Exception as e:
        logger.error(f"_build_strategy error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Metric label helper
# ─────────────────────────────────────────────────────────────────────────────

class _MetricBox(QWidget):
    """Piccola card con etichetta + valore."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        self._lbl_name = QLabel(label)
        self._lbl_name.setStyleSheet("color:#8b949e; font-size:10px;")
        self._lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl_val = QLabel("—")
        self._lbl_val.setStyleSheet(
            "color:#e6edf3; font-size:14px; font-weight:bold;"
        )
        self._lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._lbl_name)
        layout.addWidget(self._lbl_val)
        self.setStyleSheet(_METRIC_STYLE_BASE)

    def set_value(self, text: str, color: str = "#e6edf3"):
        self._lbl_val.setText(text)
        self._lbl_val.setStyleSheet(
            f"color:{color}; font-size:14px; font-weight:bold;"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pannello principale
# ─────────────────────────────────────────────────────────────────────────────

class BacktestPanel(QWidget):
    """
    Pannello completo per configurare ed eseguire backtest.

    Layout:
    ┌────────────────────────────────────────────────┐
    │  [Controls row: symbol / strategy / tf / days] │
    │  [Progress bar]                                │
    ├────────────────┬───────────────────────────────┤
    │  Metrics grid  │  Equity curve (pyqtgraph)      │
    ├────────────────┴───────────────────────────────┤
    │  Trade log (QTableWidget)                       │
    └────────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#0d1117; color:#e6edf3;")
        self._worker: Optional[_BacktestWorker] = None
        self._thread: Optional[QThread] = None
        self._result: Optional[BacktestResult] = None

        uic.loadUi(str(_UI), self)
        self._apply_styles()
        self._build_metrics_grid()
        self._build_chart_content()

        # Post-load tweaks
        self._tf_combo.setCurrentText("1h")
        self._splitter.setSizes([340, 220])

        # Connect signals
        self._btn_run.clicked.connect(self._on_run_clicked)
        self._btn_export.clicked.connect(self._on_export_clicked)

    # ── UI ───────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        _input = (
            "background:#161b22; border:1px solid #30363d; border-radius:4px; "
            "color:#e6edf3; padding:3px 6px;"
        )
        _gb = (
            "QGroupBox { color:#8b949e; font-size:11px; border:1px solid #21262d; "
            "border-radius:6px; margin-top:8px; padding-top:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:8px; }"
        )
        self._sym_input.setStyleSheet(_input)
        self._strat_combo.setStyleSheet(_input)
        self._tf_combo.setStyleSheet(_input)
        self._days_spin.setStyleSheet(_input)
        self._cap_spin.setStyleSheet(_input)
        self._btn_run.setStyleSheet(
            "background:#238636; color:white; border:none; border-radius:6px; "
            "font-weight:bold; padding:0 16px;"
        )
        self._btn_export.setStyleSheet(
            "background:#21262d; color:#8b949e; border:1px solid #30363d; "
            "border-radius:6px; padding:0 12px;"
        )
        self._progress.setStyleSheet(
            "QProgressBar { background:#21262d; border:none; border-radius:3px; }"
            "QProgressBar::chunk { background:#238636; border-radius:3px; }"
        )
        self._lbl_status.setStyleSheet("color:#8b949e; font-size:11px;")
        self._metrics_group.setStyleSheet(_gb)
        self._chart_group.setStyleSheet(_gb)
        self._log_group.setStyleSheet(_gb)
        self._trade_table.setStyleSheet(
            "QTableWidget { background:#0d1117; alternate-background-color:#161b22; "
            "color:#e6edf3; gridline-color:#21262d; border:none; font-size:11px; }"
            "QHeaderView::section { background:#161b22; color:#8b949e; "
            "border:none; padding:4px; font-size:11px; }"
        )
        self._trade_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _build_metrics_grid(self):
        """Popola _metrics_group (QGroupBox senza layout) con la griglia di _MetricBox."""
        grid = QGridLayout(self._metrics_group)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 12, 8, 8)
        metrics = [
            ("Rendimento",    "_m_return"),
            ("Rendim. Ann.",  "_m_ann_return"),
            ("Sharpe",        "_m_sharpe"),
            ("Sortino",       "_m_sortino"),
            ("Max Drawdown",  "_m_drawdown"),
            ("Win Rate",      "_m_winrate"),
            ("Profit Factor", "_m_pf"),
            ("N. Trade",      "_m_trades"),
            ("Avg Win",       "_m_avg_win"),
            ("Avg Loss",      "_m_avg_loss"),
            ("Capitale Fin.", "_m_final_cap"),
            ("Barre/Trade",   "_m_bars"),
        ]
        for idx, (label, attr) in enumerate(metrics):
            box = _MetricBox(label)
            setattr(self, attr, box)
            grid.addWidget(box, idx // 2, idx % 2)

    def _build_chart_content(self):
        """Popola _chart_group (QGroupBox senza layout) con pg.PlotWidget."""
        layout = QVBoxLayout(self._chart_group)
        layout.setContentsMargins(4, 12, 4, 4)
        if _PG_OK:
            pg.setConfigOption("background", "#0d1117")
            pg.setConfigOption("foreground", "#8b949e")
            self._plot_widget = pg.PlotWidget()
            self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
            self._plot_widget.getAxis("left").setLabel("Capitale (€)")
            self._plot_widget.getAxis("bottom").setLabel("Barre")
            self._plot_widget.setMinimumHeight(180)
            layout.addWidget(self._plot_widget)
            self._equity_line = self._plot_widget.plot(
                pen=pg.mkPen("#3fb950", width=2), name="Strategia"
            )
            self._bnh_line = self._plot_widget.plot(
                pen=pg.mkPen("#8b949e", width=1, style=Qt.PenStyle.DashLine),
                name="Buy & Hold"
            )
            self._plot_widget.addLegend(offset=(10, 10))
        else:
            lbl = QLabel("pyqtgraph non installato\n(pip install pyqtgraph)")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#8b949e;")
            layout.addWidget(lbl)
            self._plot_widget = None
            self._equity_line = None
            self._bnh_line = None

    # ── Slot ─────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_run_clicked(self):
        if self._thread and self._thread.isRunning():
            return  # già in esecuzione

        symbol   = self._sym_input.text().strip().upper() or "AAPL"
        strategy = self._strat_combo.currentText()
        tf       = self._tf_combo.currentText()
        days     = self._days_spin.value()
        capital  = self._cap_spin.value()

        self._reset_ui()
        self._set_running(True)
        self._lbl_status.setText(
            f"Download {symbol} [{tf}] · {days} giorni..."
        )

        # Cleanup thread/worker precedenti (già terminati per il check sopra)
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

        # Setup worker + thread
        self._worker = _BacktestWorker(symbol, strategy, tf, capital, days)
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_done)  # named slot, no lambda

        self._thread.start()

    @pyqtSlot(int)
    def _on_progress(self, pct: int):
        self._progress.setValue(pct)
        self._lbl_status.setText(f"Simulazione in corso... {pct}%")

    @pyqtSlot(object)
    def _on_finished(self, result: BacktestResult):
        self._result = result
        self._progress.setValue(100)
        self._lbl_status.setText(
            f"Completato · {result.total_trades} trade · "
            f"{result.total_return_pct:+.2f}%"
        )
        self._display_result(result)
        self._btn_export.setEnabled(True)

    @pyqtSlot()
    def _on_thread_done(self):
        self._set_running(False)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._lbl_status.setText(f"Errore: {msg}")
        self._lbl_status.setStyleSheet("color:#f85149; font-size:11px;")

    @pyqtSlot()
    def _on_export_clicked(self):
        if self._result is None:
            return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Esporta Trade Log", f"backtest_{self._result.symbol}.csv",
            "CSV (*.csv)"
        )
        if path:
            rows = []
            for t in self._result.trades:
                rows.append({
                    "symbol":      t.symbol,
                    "direction":   t.direction,
                    "entry_time":  str(t.entry_time),
                    "exit_time":   str(t.exit_time),
                    "entry_price": t.entry_price,
                    "exit_price":  t.exit_price,
                    "quantity":    t.quantity,
                    "pnl":         t.pnl,
                    "pnl_pct":     t.pnl_pct,
                    "exit_reason": t.exit_reason,
                    "bars_held":   t.bars_held,
                })
            pd.DataFrame(rows).to_csv(path, index=False)
            self._lbl_status.setText(f"Esportato: {path}")

    # ── Display ───────────────────────────────────────────────────────────────

    def _display_result(self, r: BacktestResult):
        # Colore rendimento
        ret_color = "#3fb950" if r.total_return_pct >= 0 else "#f85149"
        dd_color  = "#f85149" if r.max_drawdown_pct > 15 else (
            "#e3b341" if r.max_drawdown_pct > 8 else "#3fb950"
        )
        sharpe_color = (
            "#3fb950" if r.sharpe_ratio > 1.5 else
            "#e3b341" if r.sharpe_ratio > 0.8 else "#f85149"
        )

        self._m_return.set_value(f"{r.total_return_pct:+.2f}%", ret_color)
        self._m_ann_return.set_value(f"{r.annualized_return_pct:+.2f}%", ret_color)
        self._m_sharpe.set_value(f"{r.sharpe_ratio:.3f}", sharpe_color)
        self._m_sortino.set_value(f"{r.sortino_ratio:.3f}")
        self._m_drawdown.set_value(f"-{r.max_drawdown_pct:.2f}%", dd_color)
        self._m_winrate.set_value(
            f"{r.win_rate:.1f}%",
            "#3fb950" if r.win_rate >= 50 else "#e3b341"
        )
        self._m_pf.set_value(
            f"{r.profit_factor:.2f}",
            "#3fb950" if r.profit_factor >= 1.5 else "#e3b341"
        )
        self._m_trades.set_value(
            f"{r.total_trades} ({r.winning_trades}W / {r.losing_trades}L)"
        )
        self._m_avg_win.set_value(f"{r.avg_win_pct:+.2f}%", "#3fb950")
        self._m_avg_loss.set_value(f"{r.avg_loss_pct:+.2f}%", "#f85149")
        self._m_final_cap.set_value(f"€ {r.final_capital:,.0f}", ret_color)
        self._m_bars.set_value(f"{r.avg_bars_held:.1f}")

        # Equity curve
        if _PG_OK and self._equity_line and r.equity_curve:
            eq = np.array(r.equity_curve, dtype=float)
            xs = np.arange(len(eq))
            self._equity_line.setData(xs, eq)

            # Buy & Hold benchmark
            if len(eq) > 1:
                bnh = np.linspace(r.initial_capital, r.initial_capital, len(eq))
                # Approximazione B&H: crescita proporzionale al rendimento buy&hold
                # (non abbiamo il close reale qui — usiamo linea piatta come baseline)
                self._bnh_line.setData(xs, bnh)

        # Trade log
        self._trade_table.setRowCount(0)
        for i, t in enumerate(r.trades):
            pnl_color = QColor("#3fb950") if t.pnl > 0 else QColor("#f85149")
            dir_color = QColor("#3fb950") if t.direction == "buy" else QColor("#f85149")

            row_data = [
                str(i + 1),
                t.symbol,
                t.direction.upper(),
                str(t.entry_time)[:16],
                str(t.exit_time)[:16],
                f"{t.entry_price:.4f}",
                f"{t.exit_price:.4f}",
                f"{t.quantity:.4f}",
                f"{t.pnl:+.2f}",
                f"{t.pnl_pct:+.2f}%",
                t.exit_reason,
                str(t.bars_held),
            ]
            self._trade_table.insertRow(i)
            for col, val in enumerate(row_data):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 2:   # direzione
                    item.setForeground(dir_color)
                elif col in (8, 9):   # P&L
                    item.setForeground(pnl_color)
                self._trade_table.setItem(i, col, item)

    def _reset_ui(self):
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._lbl_status.setStyleSheet("color:#8b949e; font-size:11px;")
        self._trade_table.setRowCount(0)
        self._btn_export.setEnabled(False)

        # Reset metriche
        for attr in ("_m_return", "_m_ann_return", "_m_sharpe", "_m_sortino",
                     "_m_drawdown", "_m_winrate", "_m_pf", "_m_trades",
                     "_m_avg_win", "_m_avg_loss", "_m_final_cap", "_m_bars"):
            getattr(self, attr).set_value("—")

        if _PG_OK and self._equity_line:
            self._equity_line.setData([], [])
            self._bnh_line.setData([], [])

    def _set_running(self, running: bool):
        self._btn_run.setEnabled(not running)
        self._btn_run.setText("⏳  In corso..." if running else "▶  Avvia Backtest")
        self._progress.setVisible(running or self._result is not None)
