"""
Strategy Manager - orchestrates multiple strategies across all instruments.
Aggregates and filters signals before passing to risk manager.
"""

import asyncio
from typing import Dict, List, Optional

import pandas as pd

from strategies.base_strategy import BaseStrategy, TradeSignal
from strategies.ai_strategy import AIStrategy
from strategies.technical_strategy import (
    TrendFollowingStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    ScalpingStrategy,
)
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="strategies.manager")


class StrategyManager:
    """
    Runs all active strategies on incoming market data
    and aggregates their signals.
    """

    def __init__(self):
        self.strategies: List[BaseStrategy] = [
            AIStrategy(timeframe=settings.primary_timeframe),
            TrendFollowingStrategy(timeframe="1h"),
            MeanReversionStrategy(timeframe="1h"),
            BreakoutStrategy(timeframe="1d"),
            ScalpingStrategy(),
        ]
        logger.info(f"Strategy manager loaded {len(self.strategies)} strategies")

    async def evaluate(
        self,
        symbol: str,
        data_by_timeframe: Dict[str, pd.DataFrame],
    ) -> List[TradeSignal]:
        """
        Evaluate all strategies for a given symbol.
        Returns aggregated, filtered, and deduplicated signals.
        """
        all_signals: List[TradeSignal] = []

        for strategy in self.strategies:
            if not strategy.active:
                continue
            df = data_by_timeframe.get(strategy.timeframe)
            if df is None:
                # fallback to primary
                df = data_by_timeframe.get(settings.primary_timeframe)
            if df is None:
                continue
            try:
                signals = await asyncio.to_thread(strategy.generate_signals, symbol, df)
                for s in signals:
                    if strategy.filter_signal(s, settings.ml.min_confidence):
                        all_signals.append(s)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} error on {symbol}: {e}")

        return self._aggregate(all_signals)

    def _aggregate(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """
        If multiple strategies agree, boost confidence.
        If they disagree, reduce or cancel.
        Returns best signal per direction.
        """
        if not signals:
            return []

        buy_signals = [s for s in signals if s.direction == "buy"]
        sell_signals = [s for s in signals if s.direction == "sell"]

        result = []

        if buy_signals:
            best_buy = max(buy_signals, key=lambda s: s.confidence)
            if len(buy_signals) > 1:
                agreement_bonus = min(0.1 * (len(buy_signals) - 1), 0.2)
                best_buy.confidence = min(best_buy.confidence + agreement_bonus, 1.0)
                best_buy.metadata["agreement"] = len(buy_signals)
            result.append(best_buy)

        if sell_signals:
            best_sell = max(sell_signals, key=lambda s: s.confidence)
            if len(sell_signals) > 1:
                agreement_bonus = min(0.1 * (len(sell_signals) - 1), 0.2)
                best_sell.confidence = min(best_sell.confidence + agreement_bonus, 1.0)
                best_sell.metadata["agreement"] = len(sell_signals)
            result.append(best_sell)

        # If both buy and sell signals present, keep highest confidence
        if buy_signals and sell_signals:
            result = [max(result, key=lambda s: s.confidence)]

        return result

    async def evaluate_all(
        self,
        data: Dict[str, Dict[str, pd.DataFrame]],
    ) -> Dict[str, List[TradeSignal]]:
        """Evaluate all symbols in parallel."""
        tasks = {
            symbol: self.evaluate(symbol, timeframes)
            for symbol, timeframes in data.items()
        }
        results_list = await asyncio.gather(*tasks.values(), return_exceptions=True)
        output = {}
        for symbol, result in zip(tasks.keys(), results_list):
            if isinstance(result, Exception):
                logger.error(f"Evaluation error for {symbol}: {result}")
            elif result:
                output[symbol] = result
        return output
