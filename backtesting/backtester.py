"""
Backtesting Engine
Vectorized + event-driven backtesting with full performance analytics.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from datetime import datetime
import json

from indicators.technical import TechnicalIndicators
from strategies.base_strategy import BaseStrategy, TradeSignal
from utils.logger import get_logger

logger = get_logger.bind(name="backtesting")


@dataclass
class BacktestTrade:
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    stop_loss: float
    take_profit: float
    exit_reason: str  # "stop_loss" | "take_profit" | "signal" | "end"
    strategy: str
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    bars_held: int = 0

    def __post_init__(self):
        if self.direction == "buy":
            self.pnl = (self.exit_price - self.entry_price) * self.quantity - self.commission
            self.pnl_pct = (self.exit_price - self.entry_price) / self.entry_price * 100
        else:
            self.pnl = (self.entry_price - self.exit_price) * self.quantity - self.commission
            self.pnl_pct = (self.entry_price - self.exit_price) / self.entry_price * 100


@dataclass
class BacktestResult:
    symbol: str
    strategy: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    trades: List[BacktestTrade] = field(default_factory=list)

    # Metrics
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_bars_held: float = 0.0
    equity_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "timeframe": self.timeframe,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return_pct": self.total_return_pct,
            "annualized_return_pct": self.annualized_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win_pct": self.avg_win_pct,
            "avg_loss_pct": self.avg_loss_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_bars_held": self.avg_bars_held,
        }

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"BACKTEST: {self.symbol} | {self.strategy} | {self.timeframe}\n"
            f"Period: {self.start_date} → {self.end_date}\n"
            f"{'─'*60}\n"
            f"Total Return:     {self.total_return_pct:+.2f}%\n"
            f"Annual Return:    {self.annualized_return_pct:+.2f}%\n"
            f"Sharpe Ratio:     {self.sharpe_ratio:.3f}\n"
            f"Sortino Ratio:    {self.sortino_ratio:.3f}\n"
            f"Max Drawdown:     -{self.max_drawdown_pct:.2f}%\n"
            f"Win Rate:         {self.win_rate:.1f}%\n"
            f"Profit Factor:    {self.profit_factor:.2f}\n"
            f"Total Trades:     {self.total_trades}\n"
            f"Avg Win:          {self.avg_win_pct:+.2f}%\n"
            f"Avg Loss:         {self.avg_loss_pct:+.2f}%\n"
            f"Final Capital:    ${self.final_capital:,.2f}\n"
            f"{'='*60}"
        )


class Backtester:
    """
    Event-driven backtester.
    Supports any BaseStrategy subclass.
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        commission_pct: float = 0.001,   # 0.1% per trade
        slippage_pct: float = 0.0005,    # 0.05% slippage
        risk_pct_per_trade: float = 2.0,
    ):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.risk_pct = risk_pct_per_trade

    def run(
        self,
        df: pd.DataFrame,
        strategy: BaseStrategy,
        symbol: str,
    ) -> BacktestResult:
        logger.info(f"Backtesting {symbol} | {strategy.name}...")

        df = TechnicalIndicators.compute_all(df)
        df = df.dropna(subset=["close", "rsi_14", "macd"])

        capital = self.initial_capital
        equity_curve = [capital]
        trades: List[BacktestTrade] = []
        open_trade: Optional[dict] = None

        for i in range(50, len(df)):
            window = df.iloc[:i+1]
            bar = df.iloc[i]
            price = float(bar["close"])
            high = float(bar["high"])
            low = float(bar["low"])
            ts = bar.name

            # ── Check open trade ──────────────────────────────────────────
            if open_trade:
                exit_reason = None
                exit_price = price

                if open_trade["direction"] == "buy":
                    # Check stop hit intrabar
                    if low <= open_trade["stop_loss"]:
                        exit_price = open_trade["stop_loss"]
                        exit_reason = "stop_loss"
                    elif high >= open_trade["take_profit"]:
                        exit_price = open_trade["take_profit"]
                        exit_reason = "take_profit"
                else:
                    if high >= open_trade["stop_loss"]:
                        exit_price = open_trade["stop_loss"]
                        exit_reason = "stop_loss"
                    elif low <= open_trade["take_profit"]:
                        exit_price = open_trade["take_profit"]
                        exit_reason = "take_profit"

                if exit_reason:
                    t = self._close_trade(open_trade, exit_price, ts, exit_reason, i)
                    capital += t.pnl
                    trades.append(t)
                    open_trade = None

            # ── Generate new signal ───────────────────────────────────────
            if open_trade is None:
                try:
                    signals = strategy.generate_signals(symbol, window)
                    for sig in signals:
                        if not sig.is_actionable:
                            continue
                        entry_price = price * (1 + self.slippage_pct if sig.direction == "buy" else 1 - self.slippage_pct)
                        risk_usd = capital * (self.risk_pct / 100)
                        sl = sig.stop_loss or (entry_price * 0.98 if sig.direction == "buy" else entry_price * 1.02)
                        tp = sig.take_profit or (entry_price * 1.04 if sig.direction == "buy" else entry_price * 0.96)
                        stop_dist = abs(entry_price - sl)
                        qty = (risk_usd / stop_dist) if stop_dist > 0 else 0
                        if qty <= 0:
                            continue

                        open_trade = {
                            "symbol": symbol,
                            "direction": sig.direction,
                            "entry_price": entry_price,
                            "quantity": qty,
                            "entry_time": ts,
                            "entry_bar": i,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "strategy": strategy.name,
                        }
                        break
                except Exception as e:
                    logger.debug(f"Signal error at bar {i}: {e}")

            equity_curve.append(capital)

        # Close any remaining position at end
        if open_trade:
            last_price = float(df["close"].iloc[-1])
            t = self._close_trade(open_trade, last_price, df.index[-1], "end", len(df) - 1)
            capital += t.pnl
            trades.append(t)

        result = BacktestResult(
            symbol=symbol,
            strategy=strategy.name,
            timeframe=getattr(strategy, "timeframe", "1h"),
            start_date=str(df.index[0])[:10],
            end_date=str(df.index[-1])[:10],
            initial_capital=self.initial_capital,
            final_capital=capital,
            trades=trades,
            equity_curve=equity_curve,
        )
        self._compute_metrics(result, equity_curve)
        logger.info(result.summary())
        return result

    @staticmethod
    def _bars_per_year(timeframe: str) -> int:
        """Numero di barre per anno in base al timeframe."""
        mapping = {
            "1m":  252 * 24 * 60,  # forex: 24h/day
            "5m":  252 * 24 * 12,
            "15m": 252 * 24 * 4,
            "30m": 252 * 24 * 2,
            "1h":  252 * 24,       # forex: 6048 barre/anno
            "4h":  252 * 6,        # forex: 1512 barre/anno
            "1d":  252,
            "1w":  52,
        }
        # Normalizza: "4H" → "4h", "D1" → "1d", ecc.
        tf = timeframe.lower().replace("h", "h").strip()
        return mapping.get(tf, 252)

    def _close_trade(
        self,
        ot: dict,
        exit_price: float,
        exit_time,
        exit_reason: str,
        current_bar: int,
    ) -> BacktestTrade:
        commission = ot["entry_price"] * ot["quantity"] * self.commission_pct * 2
        return BacktestTrade(
            symbol=ot["symbol"],
            direction=ot["direction"],
            entry_price=ot["entry_price"],
            exit_price=exit_price,
            quantity=ot["quantity"],
            entry_time=ot["entry_time"],
            exit_time=exit_time,
            stop_loss=ot["stop_loss"],
            take_profit=ot["take_profit"],
            exit_reason=exit_reason,
            strategy=ot["strategy"],
            commission=commission,
            bars_held=current_bar - ot["entry_bar"],
        )

    def _compute_metrics(self, result: BacktestResult, equity: List[float]):
        trades = result.trades
        result.total_trades = len(trades)

        if not trades:
            return

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        result.winning_trades = len(wins)
        result.losing_trades = len(losses)
        result.win_rate = len(wins) / len(trades) * 100

        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        result.profit_factor = gross_profit / max(gross_loss, 1e-8)

        result.avg_win_pct = np.mean([t.pnl_pct for t in wins]) if wins else 0.0
        result.avg_loss_pct = np.mean([t.pnl_pct for t in losses]) if losses else 0.0
        result.avg_bars_held = np.mean([t.bars_held for t in trades])

        total_ret = (result.final_capital - result.initial_capital) / result.initial_capital * 100
        result.total_return_pct = total_ret

        # Bars per year: dipende dal timeframe della strategia
        bars_per_year = self._bars_per_year(result.timeframe)

        # Annualize: (total_return+1)^(bars_per_year/n_bars) - 1
        n_bars = len(equity)
        if n_bars > 1:
            result.annualized_return_pct = (
                (result.final_capital / result.initial_capital) ** (bars_per_year / max(n_bars, 1)) - 1
            ) * 100

        # Drawdown
        eq_arr = np.array(equity)
        peak = np.maximum.accumulate(eq_arr)
        dd = (peak - eq_arr) / peak * 100
        result.max_drawdown_pct = float(dd.max())

        # Sharpe & Sortino — annualizzati con sqrt(bars_per_year)
        bar_rets = np.diff(eq_arr) / eq_arr[:-1]
        if len(bar_rets) > 1 and bar_rets.std() > 0:
            result.sharpe_ratio = float(bar_rets.mean() / bar_rets.std() * np.sqrt(bars_per_year))
            neg_rets = bar_rets[bar_rets < 0]
            if len(neg_rets) > 0 and neg_rets.std() > 0:
                result.sortino_ratio = float(bar_rets.mean() / neg_rets.std() * np.sqrt(bars_per_year))
