"""
Risk Management System
- Position sizing (Kelly Criterion, fixed %, volatility-adjusted)
- Stop loss / take profit management
- Drawdown control
- Portfolio exposure limits
- Correlation checks
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from config.settings import settings
from strategies.base_strategy import TradeSignal
from utils.logger import get_logger

logger = get_logger.bind(name="risk")


@dataclass
class RiskAssessment:
    approved: bool
    symbol: str
    direction: str
    quantity: float
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]
    max_loss_usd: float
    risk_pct: float
    reason: str = ""

    def __repr__(self):
        status = "APPROVED" if self.approved else "REJECTED"
        return f"Risk[{status}] {self.symbol} {self.direction} qty={self.quantity:.4f} risk={self.risk_pct:.2f}%"


class RiskManager:
    """
    Evaluates every signal before execution.
    Applies position sizing, stop management and portfolio limits.
    """

    def __init__(self):
        self.cfg = settings.risk
        self._portfolio_value: float = 100_000.0   # updated externally
        self._open_positions: Dict[str, dict] = {}  # symbol -> position
        self._daily_pnl: float = 0.0
        self._peak_equity: float = 100_000.0
        self._current_drawdown_pct: float = 0.0

    # ── External state updates ─────────────────────────────────────────────

    def update_portfolio(
        self,
        equity: float,
        positions: Dict[str, dict],
        daily_pnl: float = 0.0,
    ):
        self._portfolio_value = equity
        self._open_positions = positions
        self._daily_pnl = daily_pnl
        if equity > self._peak_equity:
            self._peak_equity = equity
        dd = (self._peak_equity - equity) / self._peak_equity * 100
        self._current_drawdown_pct = max(0.0, dd)

    # ── Primary evaluation ─────────────────────────────────────────────────

    def evaluate(
        self,
        signal: TradeSignal,
        current_price: float,
        atr: Optional[float] = None,
    ) -> RiskAssessment:
        """Evaluate a signal and return a RiskAssessment."""

        # 1. Drawdown circuit-breaker
        if self._current_drawdown_pct >= self.cfg.max_drawdown_pct:
            return self._reject(signal, current_price, "Max drawdown reached")

        # 2. Max open positions
        if len(self._open_positions) >= self.cfg.max_open_positions:
            return self._reject(signal, current_price, "Max open positions reached")

        # 3. Duplicate position
        if signal.symbol in self._open_positions:
            return self._reject(signal, current_price, "Position already open")

        # 4. Compute stop loss
        sl, tp = self._compute_levels(signal, current_price, atr)

        # 5. Position sizing
        quantity, risk_usd, risk_pct = self._size_position(
            signal, current_price, sl
        )

        if quantity <= 0:
            return self._reject(signal, current_price, "Position size too small")

        # 6. Max position size check
        position_value = quantity * current_price
        position_pct = position_value / self._portfolio_value * 100
        if position_pct > self.cfg.max_position_size_pct:
            # Scale down
            quantity = (self.cfg.max_position_size_pct / 100 * self._portfolio_value) / current_price
            risk_usd = quantity * abs(current_price - sl)
            risk_pct = risk_usd / self._portfolio_value * 100

        # 7. Trailing stop
        trailing_stop = None
        if self.cfg.use_trailing_stop:
            trailing_dist = current_price * (self.cfg.trailing_stop_pct / 100)
            if signal.direction == "buy":
                trailing_stop = current_price - trailing_dist
            else:
                trailing_stop = current_price + trailing_dist

        return RiskAssessment(
            approved=True,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=round(quantity, 6),
            stop_loss=round(sl, 5),
            take_profit=round(tp, 5),
            trailing_stop=round(trailing_stop, 5) if trailing_stop else None,
            max_loss_usd=round(risk_usd, 2),
            risk_pct=round(risk_pct, 3),
        )

    # ── Position sizing methods ────────────────────────────────────────────

    def _size_position(
        self,
        signal: TradeSignal,
        price: float,
        stop_loss: float,
    ) -> Tuple[float, float, float]:
        """
        Kelly-adjusted position sizing.
        Returns (quantity, risk_usd, risk_pct)
        """
        # Risk per trade in USD
        risk_usd = self._portfolio_value * (self.cfg.max_portfolio_risk_pct / 100)

        # Distance from price to stop
        stop_dist = abs(price - stop_loss)
        if stop_dist < 1e-8:
            return 0.0, 0.0, 0.0

        # Base quantity from fixed risk
        base_qty = risk_usd / stop_dist

        # Scale by confidence (Kelly-like)
        kelly_qty = base_qty * signal.confidence * self.cfg.kelly_fraction

        actual_risk = kelly_qty * stop_dist
        risk_pct = actual_risk / self._portfolio_value * 100

        return kelly_qty, actual_risk, risk_pct

    def _compute_levels(
        self,
        signal: TradeSignal,
        price: float,
        atr: Optional[float],
    ) -> Tuple[float, float]:
        """Determine stop loss and take profit levels."""
        if signal.stop_loss and signal.take_profit:
            return signal.stop_loss, signal.take_profit

        if atr and atr > 0:
            if signal.direction == "buy":
                sl = price - 2.0 * atr
                tp = price + 3.0 * atr
            else:
                sl = price + 2.0 * atr
                tp = price - 3.0 * atr
        else:
            sl_pct = self.cfg.default_stop_loss_pct / 100
            tp_pct = self.cfg.default_take_profit_pct / 100
            if signal.direction == "buy":
                sl = price * (1 - sl_pct)
                tp = price * (1 + tp_pct)
            else:
                sl = price * (1 + sl_pct)
                tp = price * (1 - tp_pct)

        return sl, tp

    # ── Trailing stop updates ──────────────────────────────────────────────

    def update_trailing_stop(
        self,
        symbol: str,
        direction: str,
        current_price: float,
        current_trailing: float,
    ) -> Optional[float]:
        """Return updated trailing stop or None if not moved."""
        dist = current_price * (self.cfg.trailing_stop_pct / 100)

        if direction == "buy":
            new_trail = current_price - dist
            if new_trail > current_trailing:
                return round(new_trail, 5)
        else:
            new_trail = current_price + dist
            if new_trail < current_trailing:
                return round(new_trail, 5)

        return None

    def check_stops(
        self,
        symbol: str,
        direction: str,
        current_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Optional[str]:
        """
        Returns "stop_loss", "take_profit", or None.
        """
        if direction == "buy":
            if current_price <= stop_loss:
                return "stop_loss"
            if current_price >= take_profit:
                return "take_profit"
        else:
            if current_price >= stop_loss:
                return "stop_loss"
            if current_price <= take_profit:
                return "take_profit"
        return None

    # ── Portfolio analytics ────────────────────────────────────────────────

    @property
    def portfolio_heat(self) -> float:
        """% of portfolio at risk across all open positions."""
        total_risk = sum(
            p.get("risk_usd", 0) for p in self._open_positions.values()
        )
        return total_risk / max(self._portfolio_value, 1e-10) * 100

    @property
    def drawdown_pct(self) -> float:
        return self._current_drawdown_pct

    def can_trade(self) -> Tuple[bool, str]:
        if self._current_drawdown_pct >= self.cfg.max_drawdown_pct:
            return False, f"Drawdown {self._current_drawdown_pct:.1f}% exceeds limit {self.cfg.max_drawdown_pct}%"
        if len(self._open_positions) >= self.cfg.max_open_positions:
            return False, f"Max positions ({self.cfg.max_open_positions}) reached"
        return True, "OK"

    # ── Helpers ────────────────────────────────────────────────────────────

    def _reject(
        self,
        signal: TradeSignal,
        price: float,
        reason: str,
    ) -> RiskAssessment:
        logger.warning(f"Signal rejected [{signal.symbol}]: {reason}")
        return RiskAssessment(
            approved=False,
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            trailing_stop=None,
            max_loss_usd=0.0,
            risk_pct=0.0,
            reason=reason,
        )
