"""
TimeframeSelector — Selezione automatica del timeframe ottimale per ogni strumento.

Per ogni timeframe candidato calcola un punteggio di "qualità del segnale"
su 3 componenti matematiche:

  1. Hurst Signal   (35%) — abs(H - 0.5) × 2
     → 0 = random walk puro, 1 = forte struttura (trend o mean-rev)

  2. Cycle Clarity  (35%) — 1 / (1 + |dominant_period - ideal_bars|)
     → picco quando il ciclo dominante FFT ≈ 20 barre (finestra standard indicatori)

  3. Autocorrelation (30%) — abs(autocorr(returns, lag=1))
     → qualsiasi memoria nei ritorni = maggiore prevedibilità

Score finale: 0.35 × hurst + 0.35 × cycle + 0.30 × autocorr
Vincitore: argmax(score) tra i timeframe disponibili con dati sufficienti.
"""

from typing import Dict, Optional
import numpy as np
import pandas as pd

from indicators.cycle_analysis import HurstExponent, DominantCycle
from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="models.timeframe_selector")


class TimeframeSelector:
    """
    Seleziona il timeframe ottimale per un simbolo analizzando
    la struttura statistica dei prezzi su timeframe multipli.

    Viene istanziato una volta in AutoConfig e riutilizzato per ogni simbolo.
    Non ha stato interno per-simbolo: è stateless e thread-safe.
    """

    def select(
        self,
        data_by_tf: Dict[str, pd.DataFrame],
        symbol: str = "",
    ) -> str:
        """
        Ritorna il timeframe con il punteggio più alto.

        Parameters
        ----------
        data_by_tf : dict  {timeframe_str: pd.DataFrame(OHLCV)}
        symbol     : str   usato solo per logging

        Returns
        -------
        str  — uno dei timeframe in data_by_tf, oppure settings.primary_timeframe
               come fallback se nessun TF ha dati sufficienti.
        """
        min_bars = settings.tf_selector.min_bars
        ideal    = settings.tf_selector.ideal_cycle_bars

        scores: Dict[str, float] = {}

        for tf, df in data_by_tf.items():
            if df is None or len(df) < min_bars:
                continue
            close = df["close"].dropna()
            if len(close) < min_bars:
                continue

            try:
                H          = HurstExponent.compute(close)
                dom_period = DominantCycle.fft_period(close)
                returns    = close.pct_change().dropna()
                ac         = float(returns.autocorr(lag=1)) if len(returns) > 10 else 0.0
                if np.isnan(ac):
                    ac = 0.0

                hurst_score = abs(H - 0.5) * 2                   # [0, 1]
                cycle_score = 1.0 / (1.0 + abs(dom_period - ideal))  # [0, 1]
                ac_score    = abs(ac)                              # [0, 1]

                score = 0.35 * hurst_score + 0.35 * cycle_score + 0.30 * ac_score
                scores[tf] = round(score, 4)

                logger.debug(
                    f"{symbol}|{tf} H={H:.3f} cyc={dom_period} ac={ac:.3f} "
                    f"→ score={score:.4f}"
                )

            except Exception as e:
                logger.debug(f"TimeframeSelector error on {symbol}|{tf}: {e}")
                continue

        if not scores:
            logger.debug(
                f"{symbol}: nessun TF valido, uso fallback {settings.primary_timeframe}"
            )
            return settings.primary_timeframe

        best_tf    = max(scores, key=scores.get)
        best_score = scores[best_tf]
        logger.info(
            f"[TFSelector] {symbol} → optimal TF: {best_tf} "
            f"(score={best_score:.4f}, candidati={scores})"
        )
        return best_tf
