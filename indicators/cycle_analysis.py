"""
Cycle Analysis - Hurst exponent, dominant cycle detection, market regime.

References:
  - Hurst (1951) R/S analysis for long-range memory
  - Ehlers (2001) "Rocket Science for Traders" for cycle indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional


class HurstExponent:
    """
    Compute the Hurst exponent via Rescaled Range (R/S) analysis.

    H > 0.55  →  trending (persistent)
    H ≈ 0.50  →  random walk
    H < 0.45  →  mean-reverting (anti-persistent)
    """

    WINDOWS = [10, 15, 20, 30, 40, 60, 80, 100]

    @classmethod
    def compute(
        cls,
        close: pd.Series,
        min_window: int = 10,
        max_window: int = 100,
    ) -> float:
        """Return Hurst exponent in [0, 1]. Returns 0.5 on insufficient data."""
        returns = close.pct_change().dropna()
        n = len(returns)
        if n < 30:
            return 0.5

        windows = [w for w in cls.WINDOWS if min_window <= w <= min(max_window, n)]
        if len(windows) < 3:
            windows = [max(10, n // 8), n // 4, n // 2]
            windows = sorted(set(windows))

        log_rs = []
        log_n = []

        for w in windows:
            rs_values = []
            # Use non-overlapping subseries of length w
            for start in range(0, n - w + 1, w):
                sub = returns.iloc[start : start + w].values
                mean = sub.mean()
                if abs(mean) < 1e-10:
                    continue
                deviations = sub - mean
                cumulative = np.cumsum(deviations)
                R = cumulative.max() - cumulative.min()
                S = sub.std(ddof=1)
                if S > 0:
                    rs_values.append(R / S)

            if rs_values:
                log_rs.append(np.log(np.mean(rs_values)))
                log_n.append(np.log(w))

        if len(log_rs) < 2:
            return 0.5

        # Linear regression on log-log plot
        coeffs = np.polyfit(log_n, log_rs, 1)
        hurst = float(np.clip(coeffs[0], 0.0, 1.0))
        return round(hurst, 4)


class DominantCycle:
    """
    Detect dominant market cycle period using FFT on de-trended price.
    Also computes instantaneous cycle phase.
    """

    @staticmethod
    def fft_period(close: pd.Series, max_period: int = 50, min_period: int = 4) -> int:
        """
        Return dominant cycle period in bars.
        Uses FFT on last 128 bars of de-trended price.
        """
        n_fft = min(128, len(close))
        if n_fft < 16:
            return 20  # default fallback

        segment = close.iloc[-n_fft:].values.astype(float)

        # De-trend: subtract EMA(40) as proxy for trend component
        ema_period = min(40, n_fft // 3)
        weights = np.exp(np.linspace(-1.0, 0.0, ema_period))
        weights /= weights.sum()
        ema = np.convolve(segment, weights[::-1], mode="same")
        detrended = segment - ema

        # Apply Hann window to reduce spectral leakage
        window = np.hanning(n_fft)
        windowed = detrended * window

        # FFT
        spectrum = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(n_fft)

        # Map frequency to period and filter to valid range
        with np.errstate(divide="ignore", invalid="ignore"):
            periods = np.where(freqs > 0, 1.0 / freqs, 0.0)

        # Mask outside valid range (escludi anche inf/nan)
        valid_mask = (periods >= min_period) & (periods <= max_period) & np.isfinite(periods)
        if not valid_mask.any():
            return 20

        filtered_spectrum = np.where(valid_mask, spectrum, 0.0)
        dominant_idx = int(np.argmax(filtered_spectrum))
        dominant_period = int(round(periods[dominant_idx]))
        return max(min_period, min(dominant_period, max_period))

    @staticmethod
    def cycle_phase(close: pd.Series, period: int) -> float:
        """
        Return current phase of dominant cycle in radians [0, 2π].
        Uses a simple sine fit over the last `period` bars.
        """
        if period <= 0 or len(close) < period:
            return 0.0

        segment = close.iloc[-period:].values.astype(float)
        segment -= segment.mean()

        t = np.linspace(0, 2 * np.pi, period)
        # Project onto sin and cos basis
        sin_coeff = np.dot(segment, np.sin(t)) / (period / 2)
        cos_coeff = np.dot(segment, np.cos(t)) / (period / 2)
        phase = float(np.arctan2(sin_coeff, cos_coeff) % (2 * np.pi))
        return round(phase, 4)

    @staticmethod
    def cycle_phase_normalized(phase: float) -> float:
        """Convert phase to -1..+1 where +1 = cycle peak, -1 = cycle trough."""
        return round(np.cos(phase), 4)


class MarketRegime:
    """
    Classify current market regime based on Hurst exponent, cycle period,
    and ADX / volatility indicators.
    """

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Compute Average Directional Index (ADX)."""
        if len(close) < period + 1:
            return 20.0

        high_arr = high.values.astype(float)
        low_arr = low.values.astype(float)
        close_arr = close.values.astype(float)

        plus_dm = np.zeros(len(close_arr))
        minus_dm = np.zeros(len(close_arr))
        tr = np.zeros(len(close_arr))

        for i in range(1, len(close_arr)):
            h_diff = high_arr[i] - high_arr[i - 1]
            l_diff = low_arr[i - 1] - low_arr[i]
            plus_dm[i] = h_diff if h_diff > l_diff and h_diff > 0 else 0.0
            minus_dm[i] = l_diff if l_diff > h_diff and l_diff > 0 else 0.0
            tr[i] = max(
                high_arr[i] - low_arr[i],
                abs(high_arr[i] - close_arr[i - 1]),
                abs(low_arr[i] - close_arr[i - 1]),
            )

        def ema_wilder(arr: np.ndarray, p: int) -> np.ndarray:
            result = np.zeros_like(arr)
            result[p] = arr[1 : p + 1].mean()
            for j in range(p + 1, len(arr)):
                result[j] = result[j - 1] * (p - 1) / p + arr[j] / p
            return result

        atr14 = ema_wilder(tr, period)
        plus_di = 100 * ema_wilder(plus_dm, period) / (atr14 + 1e-10)
        minus_di = 100 * ema_wilder(minus_dm, period) / (atr14 + 1e-10)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx_arr = ema_wilder(dx, period)
        return round(float(adx_arr[-1]), 2)

    @classmethod
    def detect(
        cls,
        df: pd.DataFrame,
        hurst: float,
        cycle_period: int,
        trending_h: float = 0.55,
        cycling_h: float = 0.45,
        adx_trend_threshold: float = 25.0,
    ) -> str:
        """
        Returns one of: "trending", "cycling", "choppy"

        Logic:
          trending : H > trending_h  AND  ADX > threshold
          cycling  : H < cycling_h   OR   (short cycle period AND low ADX)
          choppy   : everything else
        """
        try:
            adx_val = cls.adx(df["high"], df["low"], df["close"])
        except Exception:
            adx_val = 20.0

        if hurst > trending_h and adx_val > adx_trend_threshold:
            return "trending"
        elif hurst < cycling_h or (cycle_period <= 20 and adx_val < adx_trend_threshold):
            return "cycling"
        else:
            return "choppy"

    @staticmethod
    def volatility_ratio(close: pd.Series, atr_series: Optional[pd.Series] = None) -> float:
        """ATR/price ratio as normalised volatility measure (0..1 range approx)."""
        if atr_series is not None and len(atr_series) > 0:
            last_atr = float(atr_series.iloc[-1])
            last_close = float(close.iloc[-1])
            if last_close > 0:
                return round(last_atr / last_close, 6)
        # Fallback: 20-bar std / price
        if len(close) >= 20:
            std = float(close.pct_change().dropna().iloc[-20:].std())
            return round(std, 6)
        return 0.01


class CycleFeatures:
    """
    Compute all cycle-related features in one pass.
    Returns a dict ready to merge into indicator dataframe or strategy metadata.
    """

    @staticmethod
    def compute_all(
        df: pd.DataFrame,
        hurst_max_window: int = 100,
        fft_max_period: int = 50,
    ) -> Dict:
        """
        df must have columns: open, high, low, close, volume
        Returns dict with keys:
          hurst, dominant_period, cycle_phase, cycle_phase_norm,
          regime, adx, volatility_ratio
        """
        close = df["close"]
        result: Dict = {}

        # ── Hurst exponent ──────────────────────────────────────────────
        result["hurst"] = HurstExponent.compute(close, max_window=hurst_max_window)

        # ── Dominant cycle ──────────────────────────────────────────────
        dominant_period = DominantCycle.fft_period(close, max_period=fft_max_period)
        result["dominant_period"] = dominant_period

        phase = DominantCycle.cycle_phase(close, dominant_period)
        result["cycle_phase"] = phase
        result["cycle_phase_norm"] = DominantCycle.cycle_phase_normalized(phase)
        result["cycle_phase_sin"] = round(float(np.sin(phase)), 4)
        result["cycle_phase_cos"] = round(float(np.cos(phase)), 4)

        # ── ADX ─────────────────────────────────────────────────────────
        if "high" in df.columns and "low" in df.columns:
            adx_val = MarketRegime.adx(df["high"], df["low"], close)
        else:
            adx_val = 20.0
        result["adx"] = adx_val

        # ── Regime ──────────────────────────────────────────────────────
        result["regime"] = MarketRegime.detect(df, result["hurst"], dominant_period)

        # ── Volatility ratio ────────────────────────────────────────────
        result["volatility_ratio"] = MarketRegime.volatility_ratio(close)

        return result
