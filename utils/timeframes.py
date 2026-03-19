"""Timeframe utilities"""

from typing import Optional
import pandas as pd

TIMEFRAME_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "30m": "30m",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1d",
    "1w":  "1wk",
    "1M":  "1mo",
}

TIMEFRAME_SECONDS = {
    "1m":  60,
    "5m":  300,
    "15m": 900,
    "30m": 1800,
    "1h":  3600,
    "4h":  14400,
    "1d":  86400,
    "1w":  604800,
}

YFINANCE_PERIOD_MAP = {
    "1m":  ("7d",  "1m"),
    "5m":  ("60d", "5m"),
    "15m": ("60d", "15m"),
    "30m": ("60d", "30m"),
    "1h":  ("730d","1h"),
    "4h":  ("730d","1h"),   # resample from 1h
    "1d":  ("5y",  "1d"),
    "1w":  ("10y", "1wk"),
}


def resample_ohlcv(df: pd.DataFrame, target_tf: str) -> pd.DataFrame:
    """Resample OHLCV dataframe to a higher timeframe."""
    rule_map = {
        "4h": "4H",
        "1d": "D",
        "1w": "W",
    }
    rule = rule_map.get(target_tf)
    if rule is None:
        return df

    resampled = df.resample(rule).agg({
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }).dropna()
    return resampled


def timeframe_to_seconds(tf: str) -> int:
    return TIMEFRAME_SECONDS.get(tf, 3600)
