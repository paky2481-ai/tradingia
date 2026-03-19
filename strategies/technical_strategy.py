"""
Rule-based technical strategies: Trend Following, Mean Reversion, Breakout
"""

import pandas as pd
import numpy as np
from typing import List, Optional

from strategies.base_strategy import BaseStrategy, TradeSignal
from indicators.technical import TechnicalIndicators
from utils.logger import get_logger

logger = get_logger.bind(name="strategies.technical")


class TrendFollowingStrategy(BaseStrategy):
    """EMA crossover + RSI + MACD confirmation."""
    name = "trend_following"

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        if len(df) < 200:
            return []

        df = TechnicalIndicators.compute_all(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # EMA crossover
        ema_cross_up = (last["ema_9"] > last["ema_21"]) and (prev["ema_9"] <= prev["ema_21"])
        ema_cross_down = (last["ema_9"] < last["ema_21"]) and (prev["ema_9"] >= prev["ema_21"])

        # Trend filter
        bullish_trend = last["close"] > last["sma_200"]
        bearish_trend = last["close"] < last["sma_200"]

        # Momentum confirmation
        macd_bull = last["macd"] > last["macd_signal"] and last["macd_hist"] > 0
        macd_bear = last["macd"] < last["macd_signal"] and last["macd_hist"] < 0

        rsi_not_overbought = last["rsi_14"] < 70
        rsi_not_oversold = last["rsi_14"] > 30

        signals = []
        price = float(last["close"])
        atr = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else price * 0.01

        if ema_cross_up and bullish_trend and macd_bull and rsi_not_overbought:
            conf = self._calc_confidence(last, "buy")
            signals.append(TradeSignal(
                symbol=symbol,
                direction="buy",
                confidence=conf,
                strategy_name=self.name,
                price=price,
                stop_loss=price - 2.0 * atr,
                take_profit=price + 3.0 * atr,
                timeframe=self.timeframe,
            ))

        elif ema_cross_down and bearish_trend and macd_bear and rsi_not_oversold:
            conf = self._calc_confidence(last, "sell")
            signals.append(TradeSignal(
                symbol=symbol,
                direction="sell",
                confidence=conf,
                strategy_name=self.name,
                price=price,
                stop_loss=price + 2.0 * atr,
                take_profit=price - 3.0 * atr,
                timeframe=self.timeframe,
            ))

        return signals

    def _calc_confidence(self, row: pd.Series, direction: str) -> float:
        score = 0.0
        factors = 0
        if direction == "buy":
            if row.get("above_sma50", 0) == 1:
                score += 1; factors += 1
            if row.get("above_sma200", 0) == 1:
                score += 1; factors += 1
            if 30 < row.get("rsi_14", 50) < 70:
                score += 1; factors += 1
            if row.get("macd_hist", 0) > 0:
                score += 1; factors += 1
            if row.get("volume_ratio", 1) > 1.2:
                score += 1; factors += 1
        else:
            if row.get("above_sma50", 1) == 0:
                score += 1; factors += 1
            if row.get("above_sma200", 1) == 0:
                score += 1; factors += 1
            if row.get("rsi_14", 50) > 60:
                score += 1; factors += 1
            if row.get("macd_hist", 0) < 0:
                score += 1; factors += 1
            if row.get("volume_ratio", 1) > 1.2:
                score += 1; factors += 1
        return score / max(factors, 1)


class MeanReversionStrategy(BaseStrategy):
    """Bollinger Bands + RSI mean reversion."""
    name = "mean_reversion"

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        if len(df) < 60:
            return []

        df = TechnicalIndicators.compute_all(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        price = float(last["close"])
        bb_lower = float(last["bb_lower"])
        bb_upper = float(last["bb_upper"])
        rsi = float(last["rsi_14"])
        atr = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else price * 0.01

        signals = []

        # Oversold: price below lower BB and RSI < 30, reverting up
        if (prev["close"] < prev["bb_lower"]) and (price > bb_lower) and rsi < 40:
            signals.append(TradeSignal(
                symbol=symbol,
                direction="buy",
                confidence=max(0.3, (40 - rsi) / 40),
                strategy_name=self.name,
                price=price,
                stop_loss=price - 1.5 * atr,
                take_profit=float(last["bb_middle"]),
                timeframe=self.timeframe,
            ))

        # Overbought: price above upper BB and RSI > 70
        elif (prev["close"] > prev["bb_upper"]) and (price < bb_upper) and rsi > 60:
            signals.append(TradeSignal(
                symbol=symbol,
                direction="sell",
                confidence=max(0.3, (rsi - 60) / 40),
                strategy_name=self.name,
                price=price,
                stop_loss=price + 1.5 * atr,
                take_profit=float(last["bb_middle"]),
                timeframe=self.timeframe,
            ))

        return signals


class BreakoutStrategy(BaseStrategy):
    """Donchian channel breakout with volume confirmation."""
    name = "breakout"

    def __init__(self, *args, channel_period: int = 20, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_period = channel_period

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        if len(df) < self.channel_period + 10:
            return []

        df = TechnicalIndicators.compute_all(df)
        dc_upper, dc_mid, dc_lower = TechnicalIndicators.donchian_channels(
            df["high"], df["low"], self.channel_period
        )

        last = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(last["close"])
        atr = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else price * 0.01
        high_break = float(dc_upper.iloc[-2])
        low_break = float(dc_lower.iloc[-2])
        vol_surge = last.get("volume_ratio", 1.0) > 1.5

        signals = []

        if price > high_break and prev["close"] <= high_break and vol_surge:
            signals.append(TradeSignal(
                symbol=symbol,
                direction="buy",
                confidence=min(0.85, 0.6 + (last.get("volume_ratio", 1) - 1.5) * 0.1),
                strategy_name=self.name,
                price=price,
                stop_loss=price - 2.0 * atr,
                take_profit=price + 4.0 * atr,
                timeframe=self.timeframe,
            ))
        elif price < low_break and prev["close"] >= low_break and vol_surge:
            signals.append(TradeSignal(
                symbol=symbol,
                direction="sell",
                confidence=min(0.85, 0.6 + (last.get("volume_ratio", 1) - 1.5) * 0.1),
                strategy_name=self.name,
                price=price,
                stop_loss=price + 2.0 * atr,
                take_profit=price - 4.0 * atr,
                timeframe=self.timeframe,
            ))

        return signals


class ScalpingStrategy(BaseStrategy):
    """Fast scalping using 1m/5m with RSI + Stochastic + VWAP."""
    name = "scalping"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, timeframe="5m", **kwargs)

    def generate_signals(self, symbol: str, df: pd.DataFrame) -> List[TradeSignal]:
        if len(df) < 50:
            return []

        df = TechnicalIndicators.compute_all(df)
        last = df.iloc[-1]
        price = float(last["close"])
        atr = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else price * 0.005

        vwap = float(last.get("vwap", price))
        stoch_k = float(last.get("stoch_k", 50))
        stoch_d = float(last.get("stoch_d", 50))
        rsi = float(last.get("rsi_7", 50))

        signals = []

        # Long: price above VWAP, stoch crossover from oversold
        if (price > vwap and stoch_k > stoch_d and stoch_k < 30 and rsi < 40):
            signals.append(TradeSignal(
                symbol=symbol,
                direction="buy",
                confidence=0.65,
                strategy_name=self.name,
                price=price,
                stop_loss=price - 1.0 * atr,
                take_profit=price + 1.5 * atr,
                timeframe=self.timeframe,
            ))

        elif (price < vwap and stoch_k < stoch_d and stoch_k > 70 and rsi > 60):
            signals.append(TradeSignal(
                symbol=symbol,
                direction="sell",
                confidence=0.65,
                strategy_name=self.name,
                price=price,
                stop_loss=price + 1.0 * atr,
                take_profit=price - 1.5 * atr,
                timeframe=self.timeframe,
            ))

        return signals
