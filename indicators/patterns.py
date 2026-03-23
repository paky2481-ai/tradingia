"""
Pattern Recognition Module

Rileva pattern candlestick (1-3 candele) e chart pattern (10-60 barre)
su dati OHLCV. Tutti i metodi sono statici/classmethod — nessuno stato interno.

Gerarchia dei pattern:
  Candlestick single  : Doji, Hammer, Shooting Star, Inverted Hammer, Hanging Man,
                        Bullish/Bearish Marubozu, Spinning Top
  Candlestick double  : Bullish/Bearish Engulfing, Harami, Piercing Line,
                        Dark Cloud Cover, Tweezer Top/Bottom
  Candlestick triple  : Morning Star, Evening Star, Three White Soldiers,
                        Three Black Crows
  Chart pattern       : Double Top/Bottom, Head & Shoulders, Inverse H&S,
                        Ascending/Descending/Symmetrical Triangle,
                        Bull/Bear Flag, Rising/Falling Wedge

RawPattern.confirmation_price:
  Bullish pattern → confermato quando close > confirmation_price
  Bearish pattern → confermato quando close < confirmation_price
  Neutral         → confermato dopo 1 barra
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from config.settings import settings


@dataclass
class RawPattern:
    name: str
    direction: str              # "bullish" | "bearish" | "neutral"
    confidence: float           # 0.0–1.0
    bars_involved: int
    invalidation_price: float   # prezzo che invalida il pattern
    confirmation_price: float   # prezzo da rompere per conferma
    target_price: Optional[float]
    timeframe: str
    detected_at: datetime
    metadata: Dict = field(default_factory=dict)

    @property
    def reverses_direction(self) -> Optional[str]:
        """Direzione di posizione che questo pattern invertirebbe."""
        if self.direction == "bullish":
            return "sell"
        elif self.direction == "bearish":
            return "buy"
        return None


class PatternDetector:
    """
    Rileva pattern tecnici su DataFrame OHLCV.
    Le colonne devono essere lowercase: open, high, low, close, volume.
    Almeno 10 barre per i candlestick, 30+ per i chart pattern.
    """

    # ── Public API ─────────────────────────────────────────────────────────

    @classmethod
    def detect_all(cls, df: pd.DataFrame, timeframe: str = "1h") -> List[RawPattern]:
        """Rileva tutti i pattern (candlestick + chart)."""
        df = cls._prep(df)
        out: List[RawPattern] = []
        if settings.pattern.candlestick_enabled and len(df) >= 3:
            out.extend(cls._detect_candlestick(df, timeframe))
        if settings.pattern.chart_patterns_enabled and len(df) >= 30:
            out.extend(cls._detect_chart(df, timeframe))
        return out

    @classmethod
    def detect_candlestick(cls, df: pd.DataFrame, timeframe: str = "1h") -> List[RawPattern]:
        df = cls._prep(df)
        return cls._detect_candlestick(df, timeframe) if len(df) >= 3 else []

    @classmethod
    def detect_chart(cls, df: pd.DataFrame, timeframe: str = "1h") -> List[RawPattern]:
        df = cls._prep(df)
        return cls._detect_chart(df, timeframe) if len(df) >= 30 else []

    @classmethod
    def detect_reversal(
        cls, df: pd.DataFrame, open_direction: str, timeframe: str = "1h"
    ) -> List[RawPattern]:
        """
        Ritorna solo pattern che segnalano inversione rispetto a open_direction.
        open_direction="buy"  → cerca pattern bearish
        open_direction="sell" → cerca pattern bullish
        """
        all_p = cls.detect_all(df, timeframe)
        want = "bearish" if open_direction == "buy" else "bullish"
        return [p for p in all_p if p.direction == want]

    # ── Pre-processing ─────────────────────────────────────────────────────

    @staticmethod
    def _prep(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                raise ValueError(f"DataFrame manca colonna '{col}'")
        if "volume" not in df.columns:
            df["volume"] = 1.0
        return df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    # ── Candlestick detection ──────────────────────────────────────────────

    @classmethod
    def _detect_candlestick(cls, df: pd.DataFrame, timeframe: str) -> List[RawPattern]:
        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values
        v = df["volume"].values
        n = len(c)

        # ATR semplificato (ultimi 14 bar)
        tr = np.maximum(
            h - l,
            np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))),
        )
        tr[0] = h[0] - l[0]
        atr = float(tr[-14:].mean()) if n >= 14 else float(tr.mean())
        atr = max(atr, 1e-10)

        vol_avg   = float(v[-10:].mean()) if n >= 10 else float(v.mean())
        vol_ratio = float(v[-1]) / (vol_avg + 1e-10)

        now       = datetime.utcnow()
        last      = float(c[-1])
        i         = n - 1
        body      = abs(c[i] - o[i])
        rng       = h[i] - l[i]
        upper_s   = h[i] - max(c[i], o[i])
        lower_s   = min(c[i], o[i]) - l[i]
        bull      = c[i] >= o[i]

        out: List[RawPattern] = []

        # ── Single candle ─────────────────────────────────────────────

        # Doji
        if rng > atr * 0.3 and body / (rng + 1e-10) < 0.1:
            out.append(RawPattern(
                name="Doji", direction="neutral",
                confidence=round(max(0.5, 1.0 - body / (rng + 1e-10)), 3),
                bars_involved=1,
                invalidation_price=h[i] + atr,
                confirmation_price=last,
                target_price=None,
                timeframe=timeframe, detected_at=now,
                metadata={"vol_ratio": round(vol_ratio, 2)},
            ))

        # Hammer (bullish)
        if (rng > atr * 0.5
                and lower_s >= 2 * body
                and upper_s <= body * 0.5
                and lower_s >= 0.6 * rng):
            out.append(RawPattern(
                name="Hammer", direction="bullish",
                confidence=round(min(0.50 + 0.20 * vol_ratio, 0.90), 3),
                bars_involved=1,
                invalidation_price=l[i] - atr * 0.2,
                confirmation_price=last,
                target_price=last + lower_s,
                timeframe=timeframe, detected_at=now,
                metadata={"lower_shadow": round(lower_s, 5)},
            ))

        # Shooting Star (bearish)
        if (rng > atr * 0.5
                and upper_s >= 2 * body
                and lower_s <= body * 0.5
                and upper_s >= 0.6 * rng):
            out.append(RawPattern(
                name="Shooting Star", direction="bearish",
                confidence=round(min(0.50 + 0.20 * vol_ratio, 0.90), 3),
                bars_involved=1,
                invalidation_price=h[i] + atr * 0.2,
                confirmation_price=last,
                target_price=last - upper_s,
                timeframe=timeframe, detected_at=now,
                metadata={"upper_shadow": round(upper_s, 5)},
            ))

        # Inverted Hammer (bullish — in downtrend)
        if (rng > atr * 0.5
                and upper_s >= 2 * body
                and lower_s <= body * 0.5
                and not bull
                and n >= 3 and c[i - 2] > c[i - 1]):
            out.append(RawPattern(
                name="Inverted Hammer", direction="bullish",
                confidence=round(min(0.45 + 0.20 * vol_ratio, 0.82), 3),
                bars_involved=1,
                invalidation_price=l[i] - atr * 0.2,
                confirmation_price=last,
                target_price=last + body + upper_s,
                timeframe=timeframe, detected_at=now, metadata={},
            ))

        # Hanging Man (bearish — in uptrend)
        if (rng > atr * 0.5
                and lower_s >= 2 * body
                and upper_s <= body * 0.5
                and n >= 3 and c[i - 2] < c[i - 1]):
            out.append(RawPattern(
                name="Hanging Man", direction="bearish",
                confidence=round(min(0.45 + 0.20 * vol_ratio, 0.82), 3),
                bars_involved=1,
                invalidation_price=h[i] + atr * 0.2,
                confirmation_price=last,
                target_price=last - lower_s,
                timeframe=timeframe, detected_at=now, metadata={},
            ))

        # Bullish Marubozu
        if bull and body >= 0.9 * rng and rng > atr * 0.5:
            out.append(RawPattern(
                name="Bullish Marubozu", direction="bullish",
                confidence=round(min(0.55 + 0.15 * vol_ratio, 0.92), 3),
                bars_involved=1,
                invalidation_price=l[i] - atr * 0.3,
                confirmation_price=last,
                target_price=last + body,
                timeframe=timeframe, detected_at=now, metadata={},
            ))

        # Bearish Marubozu
        if not bull and body >= 0.9 * rng and rng > atr * 0.5:
            out.append(RawPattern(
                name="Bearish Marubozu", direction="bearish",
                confidence=round(min(0.55 + 0.15 * vol_ratio, 0.92), 3),
                bars_involved=1,
                invalidation_price=h[i] + atr * 0.3,
                confirmation_price=last,
                target_price=last - body,
                timeframe=timeframe, detected_at=now, metadata={},
            ))

        # Spinning Top (neutral — indecisione)
        if (rng > atr * 0.3
                and body < rng * 0.35
                and upper_s > body * 0.5
                and lower_s > body * 0.5):
            out.append(RawPattern(
                name="Spinning Top", direction="neutral",
                confidence=0.50,
                bars_involved=1,
                invalidation_price=h[i] + atr,
                confirmation_price=last,
                target_price=None,
                timeframe=timeframe, detected_at=now, metadata={},
            ))

        # ── Two-candle patterns ────────────────────────────────────────

        if n >= 2:
            pi    = i - 1
            p_body = abs(c[pi] - o[pi])
            p_bull = c[pi] >= o[pi]
            p_mid  = (c[pi] + o[pi]) / 2.0

            # Bullish Engulfing
            if (not p_bull and bull
                    and o[i] <= c[pi] and c[i] >= o[pi]
                    and body > p_body):
                ratio = min(body / (p_body + 1e-10), 3.0)
                conf  = round(min(0.60 + 0.10 * ratio + 0.10 * vol_ratio, 0.95), 3)
                out.append(RawPattern(
                    name="Bullish Engulfing", direction="bullish",
                    confidence=conf, bars_involved=2,
                    invalidation_price=min(l[i], l[pi]) - atr * 0.2,
                    confirmation_price=last,
                    target_price=last + (c[i] - o[pi]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Bearish Engulfing
            if (p_bull and not bull
                    and o[i] >= c[pi] and c[i] <= o[pi]
                    and body > p_body):
                ratio = min(body / (p_body + 1e-10), 3.0)
                conf  = round(min(0.60 + 0.10 * ratio + 0.10 * vol_ratio, 0.95), 3)
                out.append(RawPattern(
                    name="Bearish Engulfing", direction="bearish",
                    confidence=conf, bars_involved=2,
                    invalidation_price=max(h[i], h[pi]) + atr * 0.2,
                    confirmation_price=last,
                    target_price=last - (o[pi] - c[i]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Bullish Harami
            if (not p_bull and bull
                    and o[i] > c[pi] and c[i] < o[pi]
                    and body < p_body * 0.5):
                out.append(RawPattern(
                    name="Bullish Harami", direction="bullish",
                    confidence=0.55, bars_involved=2,
                    invalidation_price=l[pi] - atr * 0.2,
                    confirmation_price=last,
                    target_price=last + p_body * 0.5,
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Bearish Harami
            if (p_bull and not bull
                    and o[i] < c[pi] and c[i] > o[pi]
                    and body < p_body * 0.5):
                out.append(RawPattern(
                    name="Bearish Harami", direction="bearish",
                    confidence=0.55, bars_involved=2,
                    invalidation_price=h[pi] + atr * 0.2,
                    confirmation_price=last,
                    target_price=last - p_body * 0.5,
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Piercing Line (bullish)
            if (not p_bull and bull
                    and o[i] < l[pi]
                    and c[i] > p_mid and c[i] < o[pi]):
                out.append(RawPattern(
                    name="Piercing Line", direction="bullish",
                    confidence=round(min(0.60 + 0.10 * vol_ratio, 0.88), 3),
                    bars_involved=2,
                    invalidation_price=l[i] - atr * 0.2,
                    confirmation_price=last,
                    target_price=float(o[pi]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Dark Cloud Cover (bearish)
            if (p_bull and not bull
                    and o[i] > h[pi]
                    and c[i] < p_mid and c[i] > o[pi]):
                out.append(RawPattern(
                    name="Dark Cloud Cover", direction="bearish",
                    confidence=round(min(0.60 + 0.10 * vol_ratio, 0.88), 3),
                    bars_involved=2,
                    invalidation_price=h[i] + atr * 0.2,
                    confirmation_price=last,
                    target_price=float(o[pi]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Tweezer Bottom (bullish)
            if (abs(l[i] - l[pi]) / (atr + 1e-10) < 0.15
                    and not p_bull and bull):
                out.append(RawPattern(
                    name="Tweezer Bottom", direction="bullish",
                    confidence=0.58, bars_involved=2,
                    invalidation_price=l[i] - atr * 0.3,
                    confirmation_price=last,
                    target_price=last + (last - l[i]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Tweezer Top (bearish)
            if (abs(h[i] - h[pi]) / (atr + 1e-10) < 0.15
                    and p_bull and not bull):
                out.append(RawPattern(
                    name="Tweezer Top", direction="bearish",
                    confidence=0.58, bars_involved=2,
                    invalidation_price=h[i] + atr * 0.3,
                    confirmation_price=last,
                    target_price=last - (h[i] - last),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

        # ── Three-candle patterns ──────────────────────────────────────

        if n >= 3:
            pi    = i - 1
            ppi   = i - 2
            p_bull  = c[pi]  >= o[pi]
            pp_bull = c[ppi] >= o[ppi]
            p_body  = abs(c[pi]  - o[pi])
            pp_body = abs(c[ppi] - o[ppi])

            # Morning Star (bullish)
            if (not pp_bull
                    and p_body < pp_body * 0.4
                    and bull
                    and body >= pp_body * 0.5
                    and c[i] > (o[ppi] + c[ppi]) / 2.0):
                out.append(RawPattern(
                    name="Morning Star", direction="bullish",
                    confidence=round(min(0.70 + 0.10 * vol_ratio, 0.92), 3),
                    bars_involved=3,
                    invalidation_price=l[pi] - atr * 0.2,
                    confirmation_price=last,
                    target_price=last + pp_body,
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Evening Star (bearish)
            if (pp_bull
                    and p_body < pp_body * 0.4
                    and not bull
                    and body >= pp_body * 0.5
                    and c[i] < (o[ppi] + c[ppi]) / 2.0):
                out.append(RawPattern(
                    name="Evening Star", direction="bearish",
                    confidence=round(min(0.70 + 0.10 * vol_ratio, 0.92), 3),
                    bars_involved=3,
                    invalidation_price=h[pi] + atr * 0.2,
                    confirmation_price=last,
                    target_price=last - pp_body,
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Three White Soldiers (bullish)
            if (bull and p_bull and pp_bull
                    and c[i] > c[pi] > c[ppi]
                    and o[i] > o[pi] > o[ppi]
                    and body > atr * 0.4
                    and p_body > atr * 0.4
                    and pp_body > atr * 0.4):
                out.append(RawPattern(
                    name="Three White Soldiers", direction="bullish",
                    confidence=0.72, bars_involved=3,
                    invalidation_price=float(l[ppi]) - atr * 0.3,
                    confirmation_price=last,
                    target_price=last + (c[i] - c[ppi]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

            # Three Black Crows (bearish)
            if (not bull and not p_bull and not pp_bull
                    and c[i] < c[pi] < c[ppi]
                    and o[i] < o[pi] < o[ppi]
                    and body > atr * 0.4
                    and p_body > atr * 0.4
                    and pp_body > atr * 0.4):
                out.append(RawPattern(
                    name="Three Black Crows", direction="bearish",
                    confidence=0.72, bars_involved=3,
                    invalidation_price=float(h[ppi]) + atr * 0.3,
                    confirmation_price=last,
                    target_price=last - (c[ppi] - c[i]),
                    timeframe=timeframe, detected_at=now, metadata={},
                ))

        return out

    # ── Chart pattern detection ────────────────────────────────────────────

    @classmethod
    def _detect_chart(cls, df: pd.DataFrame, timeframe: str) -> List[RawPattern]:
        c   = df["close"].values
        h   = df["high"].values
        l   = df["low"].values
        v   = df["volume"].values
        n   = len(c)
        now = datetime.utcnow()

        # ATR
        tr  = np.maximum(h - l, np.maximum(
            np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1))
        ))
        tr[0] = h[0] - l[0]
        atr = max(float(tr.mean()), 1e-10)

        order   = max(3, n // 20)
        peaks   = cls._find_peaks(c, order)
        troughs = cls._find_troughs(c, order)

        out: List[RawPattern] = []
        for fn in (
            cls._double_top, cls._double_bottom,
            cls._head_and_shoulders, cls._inv_head_and_shoulders,
            cls._triangle, cls._flag, cls._wedge,
        ):
            try:
                p = fn(c, h, l, v, peaks, troughs, atr, n, timeframe, now)
                if p:
                    out.append(p)
            except Exception:
                pass
        return out

    # ── Peak / trough finders ──────────────────────────────────────────────

    @staticmethod
    def _find_peaks(series: np.ndarray, order: int = 5) -> List[int]:
        result = []
        for i in range(order, len(series) - order):
            window = series[i - order: i + order + 1]
            if series[i] >= window.max():
                result.append(i)
        return result

    @staticmethod
    def _find_troughs(series: np.ndarray, order: int = 5) -> List[int]:
        result = []
        for i in range(order, len(series) - order):
            window = series[i - order: i + order + 1]
            if series[i] <= window.min():
                result.append(i)
        return result

    # ── Chart pattern helpers ──────────────────────────────────────────────

    @staticmethod
    def _double_top(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if len(peaks) < 2:
            return None
        p1, p2 = peaks[-2], peaks[-1]
        if abs(p1 - p2) < 5 or n - p2 > 5:
            return None
        price_diff = abs(c[p1] - c[p2]) / (atr + 1e-10)
        if price_diff > 2.0:
            return None
        neckline = float(l[p1: p2 + 1].min())
        height   = max(c[p1], c[p2]) - neckline
        conf = round(max(0.50, 0.82 - price_diff * 0.10), 3)
        return RawPattern(
            name="Double Top", direction="bearish",
            confidence=conf, bars_involved=p2 - p1 + 1,
            invalidation_price=max(float(c[p1]), float(c[p2])) + atr * 0.5,
            confirmation_price=neckline,
            target_price=neckline - height,
            timeframe=tf, detected_at=now,
            metadata={"peak1": p1, "peak2": p2, "neckline": round(neckline, 5)},
        )

    @staticmethod
    def _double_bottom(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if len(troughs) < 2:
            return None
        t1, t2 = troughs[-2], troughs[-1]
        if abs(t1 - t2) < 5 or n - t2 > 5:
            return None
        price_diff = abs(c[t1] - c[t2]) / (atr + 1e-10)
        if price_diff > 2.0:
            return None
        neckline = float(h[t1: t2 + 1].max())
        height   = neckline - min(c[t1], c[t2])
        conf = round(max(0.50, 0.82 - price_diff * 0.10), 3)
        return RawPattern(
            name="Double Bottom", direction="bullish",
            confidence=conf, bars_involved=t2 - t1 + 1,
            invalidation_price=min(float(c[t1]), float(c[t2])) - atr * 0.5,
            confirmation_price=neckline,
            target_price=neckline + height,
            timeframe=tf, detected_at=now,
            metadata={"trough1": t1, "trough2": t2, "neckline": round(neckline, 5)},
        )

    @staticmethod
    def _head_and_shoulders(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if len(peaks) < 3:
            return None
        ls, head, rs = peaks[-3], peaks[-2], peaks[-1]
        if not (c[head] > c[ls] and c[head] > c[rs]):
            return None
        shoulder_diff = abs(c[ls] - c[rs]) / (atr + 1e-10)
        if shoulder_diff > 2.5 or n - rs > 5:
            return None
        neckline = float((l[ls: head + 1].min() + l[head: rs + 1].min()) / 2)
        height   = float(c[head]) - neckline
        conf = round(max(0.55, 0.84 - shoulder_diff * 0.05), 3)
        return RawPattern(
            name="Head & Shoulders", direction="bearish",
            confidence=conf, bars_involved=rs - ls + 1,
            invalidation_price=float(c[head]) + atr * 0.3,
            confirmation_price=neckline,
            target_price=neckline - height,
            timeframe=tf, detected_at=now,
            metadata={"left": ls, "head": head, "right": rs, "neckline": round(neckline, 5)},
        )

    @staticmethod
    def _inv_head_and_shoulders(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if len(troughs) < 3:
            return None
        ls, head, rs = troughs[-3], troughs[-2], troughs[-1]
        if not (c[head] < c[ls] and c[head] < c[rs]):
            return None
        shoulder_diff = abs(c[ls] - c[rs]) / (atr + 1e-10)
        if shoulder_diff > 2.5 or n - rs > 5:
            return None
        neckline = float((h[ls: head + 1].max() + h[head: rs + 1].max()) / 2)
        height   = neckline - float(c[head])
        conf = round(max(0.55, 0.84 - shoulder_diff * 0.05), 3)
        return RawPattern(
            name="Inverse Head & Shoulders", direction="bullish",
            confidence=conf, bars_involved=rs - ls + 1,
            invalidation_price=float(c[head]) - atr * 0.3,
            confirmation_price=neckline,
            target_price=neckline + height,
            timeframe=tf, detected_at=now,
            metadata={"left": ls, "head": head, "right": rs, "neckline": round(neckline, 5)},
        )

    @staticmethod
    def _triangle(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if n < 20:
            return None
        window = min(30, n)
        h_w = h[-window:]
        l_w = l[-window:]
        x   = np.arange(window, dtype=float)

        h_slope = float(np.polyfit(x, h_w, 1)[0])
        l_slope = float(np.polyfit(x, l_w, 1)[0])
        h_sn    = h_slope / atr
        l_sn    = l_slope / atr

        # Verifica convergenza
        r_first = float(h_w[:5].mean() - l_w[:5].mean())
        r_last  = float(h_w[-5:].mean() - l_w[-5:].mean())
        if r_first <= 0 or r_last >= r_first * 0.80:
            return None

        price_range = float(h_w.max() - l_w.min())
        last_c      = float(c[-1])

        if abs(h_sn) < 0.12 and l_sn > 0.05:     # ascending
            return RawPattern(
                name="Ascending Triangle", direction="bullish",
                confidence=0.62, bars_involved=window,
                invalidation_price=float(l_w.min()) - atr * 0.5,
                confirmation_price=float(h_w.max()),
                target_price=float(h_w.max()) + price_range,
                timeframe=tf, detected_at=now,
                metadata={"h_slope": round(h_sn, 4), "l_slope": round(l_sn, 4)},
            )
        if h_sn < -0.05 and abs(l_sn) < 0.12:    # descending
            return RawPattern(
                name="Descending Triangle", direction="bearish",
                confidence=0.62, bars_involved=window,
                invalidation_price=float(h_w.max()) + atr * 0.5,
                confirmation_price=float(l_w.min()),
                target_price=float(l_w.min()) - price_range,
                timeframe=tf, detected_at=now,
                metadata={"h_slope": round(h_sn, 4), "l_slope": round(l_sn, 4)},
            )
        if h_sn < -0.03 and l_sn > 0.03:          # symmetrical
            trend = "bullish" if c[-1] > c[-min(20, n)] else "bearish"
            conf_p = float(h_w[-1]) if trend == "bullish" else float(l_w[-1])
            inv_p  = float(l_w.min()) - atr if trend == "bullish" else float(h_w.max()) + atr
            target = (last_c + price_range) if trend == "bullish" else (last_c - price_range)
            return RawPattern(
                name="Symmetrical Triangle", direction=trend,
                confidence=0.55, bars_involved=window,
                invalidation_price=inv_p,
                confirmation_price=conf_p,
                target_price=target,
                timeframe=tf, detected_at=now,
                metadata={"trend_bias": trend},
            )
        return None

    @staticmethod
    def _flag(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if n < 20:
            return None
        pole_len = max(5, min(8, n // 4))
        flag_len = max(8, min(12, n - pole_len - 5))
        if pole_len + flag_len > n:
            return None

        pole = c[-(pole_len + flag_len): -flag_len]
        flag = c[-flag_len:]
        pole_move = float(pole[-1] - pole[0]) / (atr * pole_len + 1e-10)
        flag_move = float(flag[-1] - flag[0]) / (atr * flag_len + 1e-10)

        v_pole = float(v[-(pole_len + flag_len): -flag_len].mean())
        v_flag = float(v[-flag_len:].mean())
        vol_ok = v_flag < v_pole * 0.85

        if pole_move > 1.5 and -1.0 < flag_move < 0.0 and vol_ok:
            ph = abs(float(pole[-1] - pole[0]))
            return RawPattern(
                name="Bull Flag", direction="bullish",
                confidence=round(0.60 + 0.08 * int(vol_ok), 3),
                bars_involved=pole_len + flag_len,
                invalidation_price=float(np.min(flag)) - atr * 0.3,
                confirmation_price=float(np.max(flag)),
                target_price=float(c[-1]) + ph,
                timeframe=tf, detected_at=now,
                metadata={"pole_move": round(pole_move, 2), "flag_move": round(flag_move, 2)},
            )
        if pole_move < -1.5 and 0.0 < flag_move < 1.0 and vol_ok:
            ph = abs(float(pole[-1] - pole[0]))
            return RawPattern(
                name="Bear Flag", direction="bearish",
                confidence=round(0.60 + 0.08 * int(vol_ok), 3),
                bars_involved=pole_len + flag_len,
                invalidation_price=float(np.max(flag)) + atr * 0.3,
                confirmation_price=float(np.min(flag)),
                target_price=float(c[-1]) - ph,
                timeframe=tf, detected_at=now,
                metadata={"pole_move": round(pole_move, 2), "flag_move": round(flag_move, 2)},
            )
        return None

    @staticmethod
    def _wedge(c, h, l, v, peaks, troughs, atr, n, tf, now) -> Optional[RawPattern]:
        if n < 20:
            return None
        window = min(25, n)
        h_w = h[-window:]
        l_w = l[-window:]
        x   = np.arange(window, dtype=float)

        h_slope = float(np.polyfit(x, h_w, 1)[0])
        l_slope = float(np.polyfit(x, l_w, 1)[0])
        h_sn    = h_slope / atr
        l_sn    = l_slope / atr

        width = float(h_w[-1] - l_w[-1])

        # Rising wedge: entrambi positivi, lows crescono più in fretta → bearish
        if h_sn > 0.02 and l_sn > 0.02 and l_sn > h_sn * 1.2:
            return RawPattern(
                name="Rising Wedge", direction="bearish",
                confidence=0.60, bars_involved=window,
                invalidation_price=float(h_w.max()) + atr * 0.5,
                confirmation_price=float(l_w[-1]),
                target_price=float(c[-1]) - width * 2,
                timeframe=tf, detected_at=now,
                metadata={"h_slope": round(h_sn, 4), "l_slope": round(l_sn, 4)},
            )
        # Falling wedge: entrambi negativi, highs scendono più in fretta → bullish
        if h_sn < -0.02 and l_sn < -0.02 and h_sn < l_sn * 1.2:
            return RawPattern(
                name="Falling Wedge", direction="bullish",
                confidence=0.60, bars_involved=window,
                invalidation_price=float(l_w.min()) - atr * 0.5,
                confirmation_price=float(h_w[-1]),
                target_price=float(c[-1]) + width * 2,
                timeframe=tf, detected_at=now,
                metadata={"h_slope": round(h_sn, 4), "l_slope": round(l_sn, 4)},
            )
        return None
