"""
Portfolio Manager
Tracks positions, P&L, performance metrics in real-time.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd

from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="portfolio")


@dataclass
class Position:
    symbol: str
    asset_type: str
    direction: str
    quantity: float
    avg_entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    strategy: str = ""
    opened_at: datetime = field(default_factory=datetime.utcnow)
    risk_usd: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        if self.direction == "buy":
            return (self.current_price - self.avg_entry_price) * self.quantity
        else:
            return (self.avg_entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_entry_price == 0:
            return 0.0
        return self.unrealized_pnl / (self.avg_entry_price * self.quantity) * 100


@dataclass
class PortfolioSnapshot:
    timestamp: datetime
    cash: float
    positions_value: float
    total_equity: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    drawdown_pct: float
    open_positions: int
    win_rate: float


class PortfolioManager:
    """
    Central portfolio state tracker.
    Handles position lifecycle: open, update, close.
    """

    def __init__(self, initial_capital: float = 100_000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[Dict] = []
        self._peak_equity = initial_capital
        self._day_start_equity = initial_capital

    # ── Position management ────────────────────────────────────────────────

    def open_position(
        self,
        symbol: str,
        asset_type: str,
        direction: str,
        quantity: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        trailing_stop: Optional[float] = None,
        strategy: str = "",
        risk_usd: float = 0.0,
    ) -> bool:
        cost = quantity * price
        if cost > self.cash:
            logger.warning(f"Insufficient cash to open {symbol}: need {cost:.2f}, have {self.cash:.2f}")
            return False

        self.cash -= cost
        self.positions[symbol] = Position(
            symbol=symbol,
            asset_type=asset_type,
            direction=direction,
            quantity=quantity,
            avg_entry_price=price,
            current_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
            strategy=strategy,
            risk_usd=risk_usd,
        )
        logger.info(f"TRADE OPEN | {direction.upper()} {quantity:.4f} {symbol} @ {price:.5f}")
        return True

    def close_position(
        self,
        symbol: str,
        price: float,
        reason: str = "manual",
    ) -> Optional[Dict]:
        if symbol not in self.positions:
            logger.warning(f"Cannot close {symbol}: not in positions")
            return None

        pos = self.positions.pop(symbol)
        proceeds = pos.quantity * price
        self.cash += proceeds

        pnl = pos.unrealized_pnl
        pnl_pct = pos.unrealized_pnl_pct

        trade_record = {
            "symbol": symbol,
            "direction": pos.direction,
            "quantity": pos.quantity,
            "entry_price": pos.avg_entry_price,
            "exit_price": price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "strategy": pos.strategy,
            "opened_at": pos.opened_at.isoformat(),
            "closed_at": datetime.utcnow().isoformat(),
            "reason": reason,
        }
        self.closed_trades.append(trade_record)

        logger.info(
            f"TRADE CLOSE | {pos.direction.upper()} {pos.quantity:.4f} {symbol} "
            f"@ {price:.5f} | PnL: {pnl:+.2f} ({pnl_pct:+.2f}%) | {reason}"
        )
        return trade_record

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all open positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    def update_trailing_stop(self, symbol: str, new_stop: float):
        if symbol in self.positions:
            self.positions[symbol].trailing_stop = new_stop

    # ── Analytics ──────────────────────────────────────────────────────────

    @property
    def total_equity(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def realized_pnl(self) -> float:
        return sum(t["pnl"] for t in self.closed_trades)

    @property
    def daily_pnl(self) -> float:
        return self.total_equity - self._day_start_equity

    @property
    def drawdown_pct(self) -> float:
        eq = self.total_equity
        if eq > self._peak_equity:
            self._peak_equity = eq
        return (self._peak_equity - eq) / self._peak_equity * 100

    @property
    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t["pnl"] > 0)
        return wins / len(self.closed_trades) * 100

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t["pnl"] for t in self.closed_trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in self.closed_trades if t["pnl"] < 0))
        return gross_profit / max(gross_loss, 1e-8)

    def get_snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            cash=self.cash,
            positions_value=sum(p.market_value for p in self.positions.values()),
            total_equity=self.total_equity,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            daily_pnl=self.daily_pnl,
            drawdown_pct=self.drawdown_pct,
            open_positions=len(self.positions),
            win_rate=self.win_rate,
        )

    def get_positions_df(self) -> pd.DataFrame:
        if not self.positions:
            return pd.DataFrame()
        data = []
        for p in self.positions.values():
            data.append({
                "symbol": p.symbol,
                "type": p.asset_type,
                "direction": p.direction,
                "quantity": p.quantity,
                "entry": p.avg_entry_price,
                "price": p.current_price,
                "value": p.market_value,
                "pnl": p.unrealized_pnl,
                "pnl%": p.unrealized_pnl_pct,
                "sl": p.stop_loss,
                "tp": p.take_profit,
                "strategy": p.strategy,
            })
        return pd.DataFrame(data)

    def get_trades_df(self) -> pd.DataFrame:
        if not self.closed_trades:
            return pd.DataFrame()
        return pd.DataFrame(self.closed_trades)

    def reset_daily(self):
        self._day_start_equity = self.total_equity

    def full_report(self) -> Dict:
        equity = self.total_equity
        return {
            "equity": equity,
            "cash": self.cash,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "daily_pnl": self.daily_pnl,
            "total_return_pct": (equity - self.initial_capital) / self.initial_capital * 100,
            "drawdown_pct": self.drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "open_positions": len(self.positions),
            "total_trades": len(self.closed_trades),
        }
