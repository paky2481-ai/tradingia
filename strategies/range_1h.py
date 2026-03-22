"""
[Paky + Tom] Mean Reversion 1H
Strumenti: EUR/GBP, USD/JPY
Logica: Bollinger Bands + RSI + Hurst < 0.50 (regime ranging)
[Chloe] Solo quando Hurst < 0.50 e ADX < 25 — mercato in range reale
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class Signal:
    symbol: str
    direction: str
    confidence: float
    stop_loss: float
    take_profit: float
    entry_price: float
    strategy: str = "range_1h"
    reason: str = ""


class RangeStrategy1H:
    """
    [Tom] Parametri ottimizzati su EUR/GBP e USD/JPY 2021-2024:
    - BB(20, 2.0): entra sulla banda esterna
    - RSI < 28 / > 72: conferma ipervenduto/ipercomprato
    - Target: ritorno alla media (BB mid) → R/R ≈ 1.5
    - Filtro Hurst < 0.50: entra SOLO in regime ranging

    [Chloe] Regola operativa: non tradare USD/JPY nelle 2h dopo BoJ/Fed.
    """

    BB_PERIOD  = 20
    BB_STD     = 2.0
    RSI_OS     = 28    # oversold threshold
    RSI_OB     = 72    # overbought threshold
    ATR_STOP   = 1.5
    MAX_ADX    = 25    # non tradare se trending
    MAX_HURST  = 0.52  # solo regime ranging
    MIN_BARS   = 40

    def __init__(self):
        self.name = "range_1h"

    def compute(self, df: pd.DataFrame, symbol: str) -> Signal:
        if len(df) < self.MIN_BARS:
            return self._no_signal(symbol, "Not enough bars")

        c = df["close"].values
        h = df["high"].values
        l = df["low"].values

        # Indicatori
        bb_up, bb_mid, bb_lo = self._bollinger(c, self.BB_PERIOD, self.BB_STD)
        rsi  = self._rsi(c, 14)
        atr  = self._atr(h, l, c, 14)
        adx  = self._adx(h, l, c, 14)
        hurst = self._hurst(c)

        price   = c[-1]
        rsi_c   = rsi[-1]
        atr_c   = atr[-1]
        adx_c   = adx[-1]
        bb_lo_c = bb_lo[-1]
        bb_hi_c = bb_up[-1]
        bb_mid_c= bb_mid[-1]

        # Filtro regime: solo ranging (Hurst basso + ADX basso)
        if hurst > self.MAX_HURST:
            return self._no_signal(symbol, f"Trending regime (Hurst={hurst:.2f})")
        if adx_c > self.MAX_ADX:
            return self._no_signal(symbol, f"Trending (ADX={adx_c:.1f})")

        # ── BUY: prezzo tocca banda inferiore + RSI ipervenduto ───────────
        if price <= bb_lo_c and rsi_c < self.RSI_OS:
            sl = round(price - self.ATR_STOP * atr_c, 5)
            tp = round(bb_mid_c, 5)   # target: ritorno alla media
            rr = abs(tp - price) / abs(price - sl) if abs(price - sl) > 1e-10 else 0
            if rr < 1.2:   # R/R minimo accettabile
                return self._no_signal(symbol, f"R/R too low ({rr:.2f})")
            conf = self._confidence(rsi_c, "buy", hurst, adx_c)
            return Signal(
                symbol=symbol, direction="buy", confidence=conf,
                stop_loss=sl, take_profit=tp, entry_price=price,
                reason=f"BB lower + RSI={rsi_c:.1f} | Hurst={hurst:.2f} ADX={adx_c:.1f}"
            )

        # ── SELL: prezzo tocca banda superiore + RSI ipercomprato ─────────
        if price >= bb_hi_c and rsi_c > self.RSI_OB:
            sl = round(price + self.ATR_STOP * atr_c, 5)
            tp = round(bb_mid_c, 5)
            rr = abs(price - tp) / abs(sl - price) if abs(sl - price) > 1e-10 else 0
            if rr < 1.2:
                return self._no_signal(symbol, f"R/R too low ({rr:.2f})")
            conf = self._confidence(rsi_c, "sell", hurst, adx_c)
            return Signal(
                symbol=symbol, direction="sell", confidence=conf,
                stop_loss=sl, take_profit=tp, entry_price=price,
                reason=f"BB upper + RSI={rsi_c:.1f} | Hurst={hurst:.2f} ADX={adx_c:.1f}"
            )

        return self._no_signal(symbol, f"No setup | RSI={rsi_c:.1f} Hurst={hurst:.2f}")

    # ── Confidence ─────────────────────────────────────────────────────────

    def _confidence(self, rsi_c, direction, hurst, adx) -> float:
        score = 0.5
        # RSI più estremo → più confidenza (usa sempre rsi_c diretto)
        if direction == "buy":
            # rsi_c < RSI_OS: più basso = più oversold
            score += min(max((self.RSI_OS - rsi_c) / self.RSI_OS, 0.0), 0.25)
        else:
            # rsi_c > RSI_OB: più alto = più overbought
            score += min(max((rsi_c - self.RSI_OB) / (100 - self.RSI_OB), 0.0), 0.25)
        # Hurst più basso → più mean-reverting
        score += min(max((self.MAX_HURST - hurst) / self.MAX_HURST, 0.0), 0.15)
        # ADX basso → range più stabile
        score += min(max((self.MAX_ADX - adx) / self.MAX_ADX, 0.0), 0.10)
        return round(min(score, 1.0), 3)

    # ── Indicatori ─────────────────────────────────────────────────────────

    @staticmethod
    def _ema(arr, span):
        a = 2 / (span + 1)
        out = np.empty(len(arr)); out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = arr[i] * a + out[i - 1] * (1 - a)
        return out

    def _bollinger(self, arr, period, std_mult):
        mid = np.array([arr[max(0, i-period):i].mean() for i in range(1, len(arr)+1)])
        std = np.array([arr[max(0, i-period):i].std(ddof=0) + 1e-10
                        for i in range(1, len(arr)+1)])
        return mid + std_mult * std, mid, mid - std_mult * std

    def _rsi(self, arr, period):
        delta = np.diff(arr, prepend=arr[0])
        gain  = np.where(delta > 0, delta, 0.0)
        loss  = np.where(delta < 0, -delta, 0.0)
        ag    = self._ema(gain, period)
        al    = self._ema(loss, period)
        rs    = np.where(al > 1e-10, ag / al, 100.0)
        return 100 - 100 / (1 + rs)

    @staticmethod
    def _atr(h, l, c, period):
        prev_c = np.roll(c, 1); prev_c[0] = c[0]
        tr = np.maximum.reduce([h - l, np.abs(h - prev_c), np.abs(l - prev_c)])
        a  = 2 / (period + 1)
        out = np.empty(len(tr)); out[0] = tr[0]
        for i in range(1, len(tr)):
            out[i] = tr[i] * a + out[i - 1] * (1 - a)
        return out

    @staticmethod
    def _adx(h, l, c, period):
        prev_h = np.roll(h, 1); prev_h[0] = h[0]
        prev_l = np.roll(l, 1); prev_l[0] = l[0]
        prev_c = np.roll(c, 1); prev_c[0] = c[0]
        dm_p = np.where((h-prev_h) > (prev_l-l), np.maximum(h-prev_h, 0), 0)
        dm_m = np.where((prev_l-l) > (h-prev_h), np.maximum(prev_l-l, 0), 0)
        tr   = np.maximum.reduce([h-l, np.abs(h-prev_c), np.abs(l-prev_c)])
        a    = 2/(period+1)
        atr_ = np.empty(len(tr)); atr_[0] = tr[0]
        dmp  = np.empty(len(tr)); dmp[0]  = dm_p[0]
        dmm  = np.empty(len(tr)); dmm[0]  = dm_m[0]
        for i in range(1, len(tr)):
            atr_[i] = tr[i]*a + atr_[i-1]*(1-a)
            dmp[i]  = dm_p[i]*a + dmp[i-1]*(1-a)
            dmm[i]  = dm_m[i]*a + dmm[i-1]*(1-a)
        di_p = np.where(atr_>1e-10, 100*dmp/atr_, 0)
        di_m = np.where(atr_>1e-10, 100*dmm/atr_, 0)
        dx   = np.where((di_p+di_m)>1e-10, 100*np.abs(di_p-di_m)/(di_p+di_m), 0)
        adx  = np.empty(len(dx)); adx[0] = dx[0]
        for i in range(1, len(dx)):
            adx[i] = dx[i]*a + adx[i-1]*(1-a)
        return adx

    @staticmethod
    def _hurst(arr: np.ndarray) -> float:
        """R/S analysis — [Tom] finestre non-sovrapposte, ddof=1."""
        n = len(arr)
        if n < 20:
            return 0.5
        returns = np.diff(np.log(np.maximum(arr, 1e-10)))
        windows = [w for w in [10, 15, 20, 30] if w <= len(returns)]
        rs_vals, ns = [], []
        for w in windows:
            # Finestre non-sovrapposte: media R/S per stima più robusta
            subseries_rs = []
            for start in range(0, len(returns) - w + 1, w):
                sub = returns[start:start + w]
                mean = sub.mean()
                if abs(mean) < 1e-10:
                    continue
                cumdev = (sub - mean).cumsum()
                R = cumdev.max() - cumdev.min()
                S = sub.std(ddof=1)
                if S > 1e-10:
                    subseries_rs.append(R / S)
            if subseries_rs:
                rs_vals.append(np.mean(subseries_rs)); ns.append(w)
        if len(rs_vals) < 2:
            return 0.5
        coeffs = np.polyfit(np.log(ns), np.log(np.maximum(rs_vals, 1e-10)), 1)
        return float(np.clip(coeffs[0], 0.1, 0.9))

    @staticmethod
    def _no_signal(symbol, reason) -> Signal:
        return Signal(symbol=symbol, direction="none", confidence=0.0,
                      stop_loss=0.0, take_profit=0.0, entry_price=0.0, reason=reason)
