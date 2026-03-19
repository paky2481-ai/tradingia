"""
Comprehensive Technical Indicators Library
Trend, Momentum, Volatility, Volume, Pattern Recognition
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict
from utils.logger import get_logger

logger = get_logger.bind(name="indicators")


class TechnicalIndicators:
    """
    Full suite of technical indicators computed on OHLCV DataFrames.
    All methods return pd.Series unless stated otherwise.
    """

    # ── Trend ──────────────────────────────────────────────────────────────

    @staticmethod
    def sma(close: pd.Series, period: int) -> pd.Series:
        return close.rolling(window=period).mean()

    @staticmethod
    def ema(close: pd.Series, period: int) -> pd.Series:
        return close.ewm(span=period, adjust=False).mean()

    @staticmethod
    def wma(close: pd.Series, period: int) -> pd.Series:
        weights = np.arange(1, period + 1)
        return close.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

    @staticmethod
    def dema(close: pd.Series, period: int) -> pd.Series:
        e = close.ewm(span=period, adjust=False).mean()
        return 2 * e - e.ewm(span=period, adjust=False).mean()

    @staticmethod
    def tema(close: pd.Series, period: int) -> pd.Series:
        e1 = close.ewm(span=period, adjust=False).mean()
        e2 = e1.ewm(span=period, adjust=False).mean()
        e3 = e2.ewm(span=period, adjust=False).mean()
        return 3 * e1 - 3 * e2 + e3

    @staticmethod
    def macd(
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Returns (macd_line, signal_line, histogram)"""
        fast_ema = close.ewm(span=fast, adjust=False).mean()
        slow_ema = close.ewm(span=slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def parabolic_sar(
        high: pd.Series,
        low: pd.Series,
        af_start: float = 0.02,
        af_step: float = 0.02,
        af_max: float = 0.2,
    ) -> pd.Series:
        """Parabolic SAR"""
        sar = pd.Series(index=high.index, dtype=float)
        bull = True
        af = af_start
        ep = low.iloc[0]
        sar.iloc[0] = high.iloc[0]

        for i in range(1, len(high)):
            prev_sar = sar.iloc[i - 1]
            if bull:
                sar.iloc[i] = prev_sar + af * (ep - prev_sar)
                sar.iloc[i] = min(sar.iloc[i], low.iloc[i - 1], low.iloc[max(0, i - 2)])
                if low.iloc[i] < sar.iloc[i]:
                    bull = False
                    sar.iloc[i] = ep
                    ep = low.iloc[i]
                    af = af_start
                else:
                    if high.iloc[i] > ep:
                        ep = high.iloc[i]
                        af = min(af + af_step, af_max)
            else:
                sar.iloc[i] = prev_sar + af * (ep - prev_sar)
                sar.iloc[i] = max(sar.iloc[i], high.iloc[i - 1], high.iloc[max(0, i - 2)])
                if high.iloc[i] > sar.iloc[i]:
                    bull = True
                    sar.iloc[i] = ep
                    ep = high.iloc[i]
                    af = af_start
                else:
                    if low.iloc[i] < ep:
                        ep = low.iloc[i]
                        af = min(af + af_step, af_max)
        return sar

    @staticmethod
    def ichimoku(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        tenkan: int = 9,
        kijun: int = 26,
        senkou_b: int = 52,
    ) -> Dict[str, pd.Series]:
        def midpoint(h, l, p):
            return (h.rolling(p).max() + l.rolling(p).min()) / 2

        tenkan_sen = midpoint(high, low, tenkan)
        kijun_sen = midpoint(high, low, kijun)
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
        senkou_b_line = midpoint(high, low, senkou_b).shift(kijun)
        chikou = close.shift(-kijun)

        return {
            "tenkan_sen": tenkan_sen,
            "kijun_sen": kijun_sen,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b_line,
            "chikou": chikou,
        }

    # ── Momentum ───────────────────────────────────────────────────────────

    @staticmethod
    def rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
        smooth_k: int = 3,
    ) -> Tuple[pd.Series, pd.Series]:
        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()
        raw_k = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
        k = raw_k.rolling(smooth_k).mean()
        d = k.rolling(d_period).mean()
        return k, d

    @staticmethod
    def cci(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 20,
    ) -> pd.Series:
        tp = (high + low + close) / 3
        ma = tp.rolling(period).mean()
        md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
        return (tp - ma) / (0.015 * md)

    @staticmethod
    def williams_r(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        hh = high.rolling(period).max()
        ll = low.rolling(period).min()
        return -100 * (hh - close) / (hh - ll + 1e-10)

    @staticmethod
    def roc(close: pd.Series, period: int = 12) -> pd.Series:
        return close.pct_change(periods=period) * 100

    @staticmethod
    def momentum(close: pd.Series, period: int = 10) -> pd.Series:
        return close - close.shift(period)

    @staticmethod
    def mfi(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        tp = (high + low + close) / 3
        raw_mf = tp * volume
        positive = raw_mf.where(tp > tp.shift(1), 0)
        negative = raw_mf.where(tp < tp.shift(1), 0)
        pos_sum = positive.rolling(period).sum()
        neg_sum = negative.rolling(period).sum()
        mfr = pos_sum / (neg_sum + 1e-10)
        return 100 - (100 / (1 + mfr))

    # ── Volatility ─────────────────────────────────────────────────────────

    @staticmethod
    def bollinger_bands(
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Returns (upper, middle, lower)"""
        middle = close.rolling(period).mean()
        std = close.rolling(period).std()
        return middle + std_dev * std, middle, middle - std_dev * std

    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    @staticmethod
    def keltner_channels(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        ema_period: int = 20,
        atr_period: int = 10,
        multiplier: float = 2.0,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        mid = close.ewm(span=ema_period, adjust=False).mean()
        atr_val = TechnicalIndicators.atr(high, low, close, atr_period)
        return mid + multiplier * atr_val, mid, mid - multiplier * atr_val

    @staticmethod
    def donchian_channels(
        high: pd.Series,
        low: pd.Series,
        period: int = 20,
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        upper = high.rolling(period).max()
        lower = low.rolling(period).min()
        middle = (upper + lower) / 2
        return upper, middle, lower

    @staticmethod
    def historical_volatility(close: pd.Series, period: int = 20) -> pd.Series:
        log_ret = np.log(close / close.shift(1))
        return log_ret.rolling(period).std() * np.sqrt(252) * 100

    # ── Volume ─────────────────────────────────────────────────────────────

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        direction = np.sign(close.diff())
        return (direction * volume).fillna(0).cumsum()

    @staticmethod
    def vwap(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
    ) -> pd.Series:
        tp = (high + low + close) / 3
        return (tp * volume).cumsum() / volume.cumsum()

    @staticmethod
    def cmf(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        period: int = 20,
    ) -> pd.Series:
        mfv = ((close - low) - (high - close)) / (high - low + 1e-10) * volume
        return mfv.rolling(period).sum() / volume.rolling(period).sum()

    @staticmethod
    def adl(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
    ) -> pd.Series:
        mf_mult = ((close - low) - (high - close)) / (high - low + 1e-10)
        mf_vol = mf_mult * volume
        return mf_vol.cumsum()

    # ── Support / Resistance ───────────────────────────────────────────────

    @staticmethod
    def pivot_points(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
    ) -> Dict[str, float]:
        """Classic pivot points for last completed bar."""
        h, l, c = high.iloc[-2], low.iloc[-2], close.iloc[-2]
        pp = (h + l + c) / 3
        return {
            "pp": pp,
            "r1": 2 * pp - l,
            "r2": pp + (h - l),
            "r3": h + 2 * (pp - l),
            "s1": 2 * pp - h,
            "s2": pp - (h - l),
            "s3": l - 2 * (h - pp),
        }

    # ── Composite ─────────────────────────────────────────────────────────

    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute a comprehensive set of indicators and append columns to df.
        df must have columns: open, high, low, close, volume
        """
        result = df.copy()
        c, h, l, v, o = df["close"], df["high"], df["low"], df["volume"], df["open"]

        # Trend
        result["sma_20"] = TechnicalIndicators.sma(c, 20)
        result["sma_50"] = TechnicalIndicators.sma(c, 50)
        result["sma_200"] = TechnicalIndicators.sma(c, 200)
        result["ema_9"] = TechnicalIndicators.ema(c, 9)
        result["ema_21"] = TechnicalIndicators.ema(c, 21)
        result["ema_50"] = TechnicalIndicators.ema(c, 50)

        macd_line, sig_line, macd_hist = TechnicalIndicators.macd(c)
        result["macd"] = macd_line
        result["macd_signal"] = sig_line
        result["macd_hist"] = macd_hist

        result["sar"] = TechnicalIndicators.parabolic_sar(h, l)

        ichi = TechnicalIndicators.ichimoku(h, l, c)
        for k, v2 in ichi.items():
            result[f"ichi_{k}"] = v2

        # Momentum
        result["rsi_14"] = TechnicalIndicators.rsi(c, 14)
        result["rsi_7"] = TechnicalIndicators.rsi(c, 7)

        k, d = TechnicalIndicators.stochastic(h, l, c)
        result["stoch_k"] = k
        result["stoch_d"] = d

        result["cci_20"] = TechnicalIndicators.cci(h, l, c, 20)
        result["williams_r"] = TechnicalIndicators.williams_r(h, l, c)
        result["roc_12"] = TechnicalIndicators.roc(c, 12)
        result["mfi_14"] = TechnicalIndicators.mfi(h, l, c, v, 14)
        result["momentum_10"] = TechnicalIndicators.momentum(c, 10)

        # Volatility
        bb_up, bb_mid, bb_low = TechnicalIndicators.bollinger_bands(c)
        result["bb_upper"] = bb_up
        result["bb_middle"] = bb_mid
        result["bb_lower"] = bb_low
        result["bb_width"] = (bb_up - bb_low) / (bb_mid + 1e-10)
        result["bb_pct"] = (c - bb_low) / (bb_up - bb_low + 1e-10)

        result["atr_14"] = TechnicalIndicators.atr(h, l, c, 14)
        result["hist_vol_20"] = TechnicalIndicators.historical_volatility(c, 20)

        kc_up, kc_mid, kc_low = TechnicalIndicators.keltner_channels(h, l, c)
        result["kc_upper"] = kc_up
        result["kc_middle"] = kc_mid
        result["kc_lower"] = kc_low

        # Volume
        result["obv"] = TechnicalIndicators.obv(c, v)
        result["vwap"] = TechnicalIndicators.vwap(h, l, c, v)
        result["cmf_20"] = TechnicalIndicators.cmf(h, l, c, v, 20)
        result["adl"] = TechnicalIndicators.adl(h, l, c, v)
        result["volume_sma_20"] = TechnicalIndicators.sma(v, 20)
        result["volume_ratio"] = v / (result["volume_sma_20"] + 1e-10)

        # Price-derived features
        result["returns"] = c.pct_change()
        result["log_returns"] = np.log(c / c.shift(1))
        result["hl_ratio"] = (h - l) / (c + 1e-10)
        result["oc_ratio"] = (c - o) / (o + 1e-10)

        # Trend signals
        result["above_sma50"] = (c > result["sma_50"]).astype(int)
        result["above_sma200"] = (c > result["sma_200"]).astype(int)
        result["golden_cross"] = (
            (result["sma_50"] > result["sma_200"]) &
            (result["sma_50"].shift(1) <= result["sma_200"].shift(1))
        ).astype(int)
        result["death_cross"] = (
            (result["sma_50"] < result["sma_200"]) &
            (result["sma_50"].shift(1) >= result["sma_200"].shift(1))
        ).astype(int)

        return result


# Convenience singleton
indicators = TechnicalIndicators()
