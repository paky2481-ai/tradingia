"""
Pattern Backtester — Valida i pattern su dati storici bar-by-bar.

Per ogni pattern rilevato:
  1. Simula il periodo di osservazione (max ttl_bars barre)
  2. Controlla se il pattern si è confermato (breakout del confirmation_price)
  3. Controlla se il target è stato raggiunto entro max_target_bars barre
  4. Accumula statistiche per pattern e timeframe

Output: List[PatternBacktestResult] — una riga per nome pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import settings
from indicators.patterns import PatternDetector, RawPattern
from utils.logger import get_logger

logger = get_logger.bind(name="backtesting.pattern")


@dataclass
class PatternBacktestResult:
    pattern_name: str
    symbol: str
    timeframe: str

    total_occurrences: int  = 0   # volte che il pattern è apparso
    confirmed_count:   int  = 0   # volte che si è confermato
    failed_count:      int  = 0   # volte che è fallito (invalidazione)
    expired_count:     int  = 0   # scaduti senza conferma

    # Statistiche sui pattern confermati
    hit_count:        int   = 0   # target raggiunto
    hit_rate:         float = 0.0 # % hit su confermati
    avg_move_pct:     float = 0.0 # % mossa media dopo conferma (positivo = nella direzione corretta)
    avg_bars_to_confirm: float = 0.0
    avg_bars_to_target:  float = 0.0

    # Equity curve simulata (1 unità per trade, long o short)
    equity_curve: List[float] = field(default_factory=lambda: [0.0])

    @property
    def confirmation_rate(self) -> float:
        if self.total_occurrences == 0:
            return 0.0
        return self.confirmed_count / self.total_occurrences

    def __str__(self) -> str:
        return (
            f"{self.pattern_name} | occ={self.total_occurrences} "
            f"conf={self.confirmation_rate:.1%} hit={self.hit_rate:.1%} "
            f"avg_move={self.avg_move_pct:+.2f}%"
        )


class PatternBacktester:
    """
    Backtest event-driven dei pattern tecnici.

    Usage:
        bt = PatternBacktester()
        results = bt.run(df, symbol="AAPL", timeframe="1h")
        for r in results:
            print(r)
    """

    def __init__(
        self,
        warmup_bars:    int = 60,
        ttl_bars:       int | None = None,
        max_target_bars: int = 20,
        min_confidence: float | None = None,
    ):
        self.warmup_bars     = warmup_bars
        self.ttl_bars        = ttl_bars or settings.pattern.ttl_bars
        self.max_target_bars = max_target_bars
        self.min_confidence  = min_confidence or settings.pattern.min_confidence

    def run(
        self,
        df: pd.DataFrame,
        symbol:        str = "UNKNOWN",
        timeframe:     str = "1h",
        pattern_names: Optional[List[str]] = None,
        progress_callback=None,
    ) -> List[PatternBacktestResult]:
        """
        Esegue il backtest bar-by-bar sul DataFrame fornito.

        Args:
            df:              OHLCV DataFrame (colonne lowercase)
            symbol:          Nome del simbolo (per output)
            timeframe:       Timeframe del df (per output)
            pattern_names:   Se specificato, testa solo questi pattern
            progress_callback: Callable(pct: int) → None

        Returns:
            Lista di PatternBacktestResult, uno per nome-pattern trovato.
        """
        # Pre-process
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                raise ValueError(f"DataFrame manca colonna '{col}'")
        if "volume" not in df.columns:
            df["volume"] = 1.0
        df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

        n = len(df)
        if n < self.warmup_bars + 10:
            logger.warning(f"Backtest: dati insufficienti ({n} barre, min={self.warmup_bars + 10})")
            return []

        # Risultati per pattern
        results: Dict[str, _PatternStats] = {}

        # Loop bar-by-bar
        for i in range(self.warmup_bars, n):
            window = df.iloc[:i]

            # Rileva pattern sulla finestra
            try:
                patterns = PatternDetector.detect_all(window, timeframe)
            except Exception:
                continue

            for raw in patterns:
                if pattern_names and raw.name not in pattern_names:
                    continue
                if raw.confidence < self.min_confidence:
                    continue

                if raw.name not in results:
                    results[raw.name] = _PatternStats(raw.name)

                stats = results[raw.name]
                stats.total += 1

                # Simula osservazione: guarda le barre future
                confirmed_bar  = None
                failed_bar     = None
                target_reached = False
                move_pct       = None

                for j in range(1, min(self.ttl_bars + 1, n - i)):
                    future_bar = df.iloc[i + j]
                    future_c   = float(future_bar["close"])
                    future_h   = float(future_bar["high"])
                    future_l   = float(future_bar["low"])

                    # Fallimento: invalidazione
                    if raw.direction == "bullish" and future_l < raw.invalidation_price:
                        failed_bar = j
                        break
                    if raw.direction == "bearish" and future_h > raw.invalidation_price:
                        failed_bar = j
                        break

                    # Conferma
                    needs_bars = 1 if raw.bars_involved <= 3 else 0
                    if j >= needs_bars + 1:
                        if raw.direction == "bullish" and future_c > raw.confirmation_price:
                            confirmed_bar = j
                            break
                        if raw.direction == "bearish" and future_c < raw.confirmation_price:
                            confirmed_bar = j
                            break
                        if raw.direction == "neutral":
                            confirmed_bar = j
                            break

                if failed_bar is not None:
                    stats.failed += 1
                elif confirmed_bar is not None:
                    stats.confirmed += 1
                    stats.bars_to_confirm.append(confirmed_bar)

                    entry_price = float(df.iloc[i + confirmed_bar]["close"])

                    # Controlla target nelle barre successive
                    target_bars_left = min(self.max_target_bars, n - (i + confirmed_bar))
                    for k in range(1, target_bars_left):
                        fb_h = float(df.iloc[i + confirmed_bar + k]["high"])
                        fb_l = float(df.iloc[i + confirmed_bar + k]["low"])
                        fb_c = float(df.iloc[i + confirmed_bar + k]["close"])

                        if raw.target_price is not None:
                            if raw.direction == "bullish" and fb_h >= raw.target_price:
                                target_reached = True
                                move_pct = (raw.target_price - entry_price) / (entry_price + 1e-10) * 100
                                stats.bars_to_target.append(k)
                                break
                            if raw.direction == "bearish" and fb_l <= raw.target_price:
                                target_reached = True
                                move_pct = (entry_price - raw.target_price) / (entry_price + 1e-10) * 100
                                stats.bars_to_target.append(k)
                                break

                    if not target_reached:
                        # Calcola mossa finale alla fine del max_target_bars
                        end_idx = min(i + confirmed_bar + self.max_target_bars, n - 1)
                        end_c   = float(df.iloc[end_idx]["close"])
                        if raw.direction == "bullish":
                            move_pct = (end_c - entry_price) / (entry_price + 1e-10) * 100
                        elif raw.direction == "bearish":
                            move_pct = (entry_price - end_c) / (entry_price + 1e-10) * 100
                        else:
                            move_pct = 0.0

                    if target_reached:
                        stats.hits += 1
                    if move_pct is not None:
                        stats.moves.append(move_pct)
                        # Equity curve: +1 se mossa positiva, -1 se negativa
                        last_equity = stats.equity[-1]
                        stats.equity.append(last_equity + (1.0 if move_pct > 0 else -1.0))

                else:
                    stats.expired += 1

            if progress_callback and i % 50 == 0:
                pct = int((i - self.warmup_bars) / (n - self.warmup_bars) * 100)
                progress_callback(pct)

        if progress_callback:
            progress_callback(100)

        # Converti in PatternBacktestResult
        output: List[PatternBacktestResult] = []
        for name, stats in sorted(results.items(), key=lambda kv: kv[1].total, reverse=True):
            r = PatternBacktestResult(
                pattern_name=name,
                symbol=symbol,
                timeframe=timeframe,
                total_occurrences=stats.total,
                confirmed_count=stats.confirmed,
                failed_count=stats.failed,
                expired_count=stats.expired,
                hit_count=stats.hits,
                hit_rate=stats.hits / max(stats.confirmed, 1),
                avg_move_pct=float(np.mean(stats.moves)) if stats.moves else 0.0,
                avg_bars_to_confirm=float(np.mean(stats.bars_to_confirm)) if stats.bars_to_confirm else 0.0,
                avg_bars_to_target=float(np.mean(stats.bars_to_target)) if stats.bars_to_target else 0.0,
                equity_curve=stats.equity,
            )
            output.append(r)
            logger.info(str(r))

        logger.info(
            f"[PatternBacktest] {symbol}/{timeframe}: "
            f"{n - self.warmup_bars} barre scansionate, "
            f"{len(output)} pattern trovati"
        )
        return output


class _PatternStats:
    """Accumulatore interno per statistiche per-pattern."""

    def __init__(self, name: str):
        self.name    = name
        self.total   = 0
        self.confirmed = 0
        self.failed    = 0
        self.expired   = 0
        self.hits      = 0
        self.moves:           List[float] = []
        self.bars_to_confirm: List[int]   = []
        self.bars_to_target:  List[int]   = []
        self.equity:          List[float] = [0.0]
