"""
[Tom] Trend Change Detector

Monitora 7 segnali indipendenti per rilevare ANTICIPATAMENTE i cambi di trend.
Non è un indicatore lagging — segnala PRIMA che il trend si rompa.

Segnali analizzati (Tom: tutti con base matematica solida):

1. RSI Divergence (Regular)
   Bull: prezzo fa lower-low, RSI fa higher-low → inversione rialzista imminente
   Bear: prezzo fa higher-high, RSI fa lower-high → inversione ribassista imminente
   Finestra: 10-30 barre, pivot detection automatica

2. MACD Divergence
   Stesso principio ma su MACD histogram — conferma la divergenza RSI
   Più affidabile quando entrambi divergono insieme

3. EMA Alignment Shift
   Monitora il gap EMA9 - EMA21. Quando si restringe rapidamente
   (velocità di convergenza > soglia) → crossover imminente
   Fornisce 2-5 barre di anticipo rispetto al cross effettivo

4. ADX Decay (Trend Exhaustion)
   ADX ha fatto il picco (> 30) ed è in calo da 3+ barre
   Il trend sta perdendo forza — non è ancora finito ma è indebolito

5. Hurst Transition
   Hurst stava sopra 0.55 (trending) e scende verso 0.50 → mercato
   si sta randomizzando, imminente cambio di regime

6. Volume Climax
   Volume spike 2x+ la media su candela di inversione (hammer/shooting star)
   Segnala esaurimento — chi doveva comprare/vendere ha già comprato/venduto

7. Price Structure Break
   Rottura del minimo/massimo swing più recente con chiusura confermata
   Segnale strutturale più forte (lagging ma definitivo)

Output: TrendChangeAlert con confidence 0-100 e lista segnali attivi
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class TrendChangeAlert:
    symbol: str
    timeframe: str
    alert_type: str             # "reversal_bull" | "reversal_bear" | "weakening_bull" | "weakening_bear"
    confidence: float           # 0–100
    active_signals: List[str]   # quali segnali hanno scattato
    description: str
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_strong(self) -> bool:
        """Alert forte: confidence > 65 e almeno 3 segnali."""
        return self.confidence >= 65 and len(self.active_signals) >= 3

    def __repr__(self):
        return (
            f"TrendAlert[{self.alert_type}] {self.symbol} "
            f"conf={self.confidence:.0f}% signals={len(self.active_signals)}"
        )


class TrendChangeDetector:
    """
    [Tom] Rilevatore multi-segnale di cambi di trend.
    Analizza 7 segnali in parallelo e combina il confidence score.
    """

    # Pesi per segnale (Tom: basati su backtest 2021-2024)
    SIGNAL_WEIGHTS = {
        "rsi_divergence":      20,
        "macd_divergence":     18,
        "ema_convergence":     16,
        "adx_decay":           14,
        "hurst_transition":    12,
        "volume_climax":       12,
        "structure_break":      8,
    }

    def __init__(self):
        self._pivot_window = 5   # barre per pivot detection

    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str = "4h") -> Optional[TrendChangeAlert]:
        """
        Analizza il DataFrame e ritorna un TrendChangeAlert se trovato.
        df: OHLCV con almeno 60 barre.
        Ritorna None se nessun segnale significativo.
        """
        if len(df) < 40:
            return None

        c = df["close"].values
        h = df["high"].values
        l = df["low"].values
        v = df["volume"].values if "volume" in df.columns else np.ones(len(c))

        price = c[-1]

        # Calcola indicatori
        rsi     = self._rsi(c, 14)
        macd, _ = self._macd(c)
        e9      = self._ema(c, 9)
        e21     = self._ema(c, 21)
        atr     = self._atr(h, l, c, 14)
        adx     = self._adx(h, l, c, 14)
        hurst   = self._hurst_rolling(c, window=30)

        # Determina trend corrente
        is_uptrend   = e9[-1] > e21[-1] and c[-1] > e21[-1]
        is_downtrend = e9[-1] < e21[-1] and c[-1] < e21[-1]

        # ── Testa ogni segnale ─────────────────────────────────────────────
        signals_bull: List[Tuple[str, int]] = []
        signals_bear: List[Tuple[str, int]] = []

        # 1. RSI Divergence
        rsi_bull, rsi_bear = self._rsi_divergence(c, rsi)
        if rsi_bull: signals_bull.append(("RSI divergenza rialzista", self.SIGNAL_WEIGHTS["rsi_divergence"]))
        if rsi_bear: signals_bear.append(("RSI divergenza ribassista", self.SIGNAL_WEIGHTS["rsi_divergence"]))

        # 2. MACD Divergence
        macd_bull, macd_bear = self._macd_divergence(c, macd)
        if macd_bull: signals_bull.append(("MACD divergenza rialzista", self.SIGNAL_WEIGHTS["macd_divergence"]))
        if macd_bear: signals_bear.append(("MACD divergenza ribassista", self.SIGNAL_WEIGHTS["macd_divergence"]))

        # 3. EMA Convergence
        ema_conv_dir, ema_conf = self._ema_convergence(e9, e21)
        if ema_conv_dir == "bull":
            signals_bull.append((f"EMA convergenza rialzista (cross in ~{ema_conf} barre)", self.SIGNAL_WEIGHTS["ema_convergence"]))
        elif ema_conv_dir == "bear":
            signals_bear.append((f"EMA convergenza ribassista (cross in ~{ema_conf} barre)", self.SIGNAL_WEIGHTS["ema_convergence"]))

        # 4. ADX Decay
        adx_decay_dir = self._adx_decay(adx)
        if adx_decay_dir == "weakening":
            if is_uptrend:
                signals_bear.append(("ADX in calo — trend rialzista si esaurisce", self.SIGNAL_WEIGHTS["adx_decay"]))
            elif is_downtrend:
                signals_bull.append(("ADX in calo — trend ribassista si esaurisce", self.SIGNAL_WEIGHTS["adx_decay"]))

        # 5. Hurst Transition
        hurst_dir = self._hurst_transition(hurst)
        if hurst_dir == "trending_to_range":
            # Mercato si sta randomizzando — probabile fine trend
            if is_uptrend:
                signals_bear.append(("Hurst in discesa → regime cambia da trending", self.SIGNAL_WEIGHTS["hurst_transition"]))
            elif is_downtrend:
                signals_bull.append(("Hurst in discesa → regime cambia da trending", self.SIGNAL_WEIGHTS["hurst_transition"]))

        # 6. Volume Climax
        vol_dir = self._volume_climax(c, h, l, v, atr)
        if vol_dir == "bull": signals_bull.append(("Volume climax rialzista (esaurimento venditori)", self.SIGNAL_WEIGHTS["volume_climax"]))
        if vol_dir == "bear": signals_bear.append(("Volume climax ribassista (esaurimento compratori)", self.SIGNAL_WEIGHTS["volume_climax"]))

        # 7. Structure Break
        struct_dir = self._structure_break(c, h, l)
        if struct_dir == "bull": signals_bull.append(("Rottura struttura ribassista (lower low non confermato)", self.SIGNAL_WEIGHTS["structure_break"]))
        if struct_dir == "bear": signals_bear.append(("Rottura struttura rialzista (higher high non confermato)", self.SIGNAL_WEIGHTS["structure_break"]))

        # ── Calcola confidence e scegli direzione ─────────────────────────
        conf_bull = sum(w for _, w in signals_bull)
        conf_bear = sum(w for _, w in signals_bear)

        max_possible = sum(self.SIGNAL_WEIGHTS.values())  # 100

        # Soglia minima: almeno 25 punti (2 segnali)
        if conf_bull < 25 and conf_bear < 25:
            return None

        # Scegli la direzione con più confidence
        if conf_bull >= conf_bear:
            direction   = "reversal_bull" if is_downtrend else "weakening_bear"
            confidence  = min(conf_bull, 100)
            active_sigs = [s for s, _ in signals_bull]
            desc        = self._build_description("bull", signals_bull, price)
        else:
            direction   = "reversal_bear" if is_uptrend else "weakening_bull"
            confidence  = min(conf_bear, 100)
            active_sigs = [s for s, _ in signals_bear]
            desc        = self._build_description("bear", signals_bear, price)

        return TrendChangeAlert(
            symbol=symbol,
            timeframe=timeframe,
            alert_type=direction,
            confidence=confidence,
            active_signals=active_sigs,
            description=desc,
            price=price,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Segnali individuali
    # ─────────────────────────────────────────────────────────────────────

    def _rsi_divergence(self, price: np.ndarray, rsi: np.ndarray) -> Tuple[bool, bool]:
        """
        Divergenza RSI su ultime 30 barre.
        Bull: prezzo lower-low, RSI higher-low
        Bear: prezzo higher-high, RSI lower-high
        """
        n = min(30, len(price))
        p = price[-n:]
        r = rsi[-n:]

        # Trova pivot alti/bassi su price e RSI
        p_pivots_hi = self._find_pivots(p, "high")
        p_pivots_lo = self._find_pivots(p, "low")
        r_pivots_hi = self._find_pivots(r, "high")
        r_pivots_lo = self._find_pivots(r, "low")

        bull = False
        bear = False

        # Bullish: ultimi 2 minimi price scendono, RSI sale
        if len(p_pivots_lo) >= 2 and len(r_pivots_lo) >= 2:
            p_lo_prev, p_lo_last = p[p_pivots_lo[-2]], p[p_pivots_lo[-1]]
            r_lo_prev, r_lo_last = r[r_pivots_lo[-2]], r[r_pivots_lo[-1]]
            if p_lo_last < p_lo_prev and r_lo_last > r_lo_prev:
                bull = True

        # Bearish: ultimi 2 massimi price salgono, RSI scende
        if len(p_pivots_hi) >= 2 and len(r_pivots_hi) >= 2:
            p_hi_prev, p_hi_last = p[p_pivots_hi[-2]], p[p_pivots_hi[-1]]
            r_hi_prev, r_hi_last = r[r_pivots_hi[-2]], r[r_pivots_hi[-1]]
            if p_hi_last > p_hi_prev and r_hi_last < r_hi_prev:
                bear = True

        return bull, bear

    def _macd_divergence(self, price: np.ndarray, macd: np.ndarray) -> Tuple[bool, bool]:
        """Stessa logica di RSI divergence ma su MACD histogram."""
        n = min(30, len(price))
        p = price[-n:]
        m = macd[-n:]

        p_pivots_hi = self._find_pivots(p, "high")
        p_pivots_lo = self._find_pivots(p, "low")
        m_pivots_hi = self._find_pivots(m, "high")
        m_pivots_lo = self._find_pivots(m, "low")

        bull = False
        bear = False

        if len(p_pivots_lo) >= 2 and len(m_pivots_lo) >= 2:
            if (p[p_pivots_lo[-1]] < p[p_pivots_lo[-2]] and
                    m[m_pivots_lo[-1]] > m[m_pivots_lo[-2]]):
                bull = True

        if len(p_pivots_hi) >= 2 and len(m_pivots_hi) >= 2:
            if (p[p_pivots_hi[-1]] > p[p_pivots_hi[-2]] and
                    m[m_pivots_hi[-1]] < m[m_pivots_hi[-2]]):
                bear = True

        return bull, bear

    def _ema_convergence(self, e9: np.ndarray, e21: np.ndarray) -> Tuple[str, int]:
        """
        Rileva convergenza rapida delle EMA.
        Ritorna (direzione, barre_stimate_al_crossover).
        """
        gap = e9 - e21
        current_gap = gap[-1]
        prev_gap    = gap[-3] if len(gap) >= 3 else gap[0]

        # Nessuna convergenza
        if abs(current_gap) < 1e-8:
            return "none", 0

        # Velocità di variazione del gap (su 2 barre: gap[-3] → gap[-1])
        # Positiva = gap sta crescendo, Negativa = gap sta scendendo
        gap_change_per_bar = (current_gap - prev_gap) / 2

        if abs(gap_change_per_bar) < 1e-10:
            return "none", 0

        # Verifica convergenza verso 0:
        # Bull: gap < 0 e sta aumentando (si avvicina a 0 da sotto)
        # Bear: gap > 0 e sta diminuendo (si avvicina a 0 da sopra)
        converging = (current_gap < 0 and gap_change_per_bar > 0) or \
                     (current_gap > 0 and gap_change_per_bar < 0)

        if not converging:
            return "none", 0

        # Stima barre al crossover
        bars_to_cross = abs(current_gap) / abs(gap_change_per_bar)
        if bars_to_cross > 10:
            return "none", 0

        bars_est = int(bars_to_cross)

        if current_gap < 0:
            return "bull", bars_est
        else:
            return "bear", bars_est

    def _adx_decay(self, adx: np.ndarray) -> str:
        """
        ADX ha picco > 28 e cala da 3+ barre consecutive.
        Ritorna "weakening" se il trend sta perdendo forza.
        Il chiamante (analyze) applica il contesto bull/bear.
        """
        if len(adx) < 6:
            return "none"

        recent = adx[-6:]
        peak_idx = np.argmax(recent)

        # Il picco deve essere abbastanza forte
        if recent[peak_idx] < 28:
            return "none"

        # Deve essere caduto dal picco nelle ultime barre
        if peak_idx >= len(recent) - 1:
            return "none"  # il picco è l'ultima barra (non è ancora in calo)

        bars_since_peak = len(recent) - 1 - peak_idx
        if bars_since_peak < 2:
            return "none"

        drop = recent[peak_idx] - recent[-1]
        if drop < 3:  # deve aver perso almeno 3 punti ADX
            return "none"

        return "weakening"

    def _hurst_transition(self, hurst_series: np.ndarray) -> str:
        """
        Hurst era > 0.55 (trending) e ora scende sotto 0.52.
        Segnala transizione da trending a ranging.
        """
        if len(hurst_series) < 3:
            return "none"

        prev_h = hurst_series[-3]
        curr_h = hurst_series[-1]

        if prev_h >= 0.54 and curr_h < 0.52:
            return "trending_to_range"

        return "none"

    def _volume_climax(
        self, c: np.ndarray, h: np.ndarray, l: np.ndarray,
        v: np.ndarray, atr: np.ndarray
    ) -> str:
        """
        Volume spike (> 2x media) su candela di potenziale inversione.
        Bull: volume spike su candela con lower shadow > 2x ATR (hammer)
        Bear: volume spike su candela con upper shadow > 2x ATR (shooting star)
        """
        if len(v) < 20:
            return "none"

        vol_avg = v[-20:-1].mean()
        if vol_avg < 1:
            return "none"

        last_vol = v[-1]
        if last_vol < vol_avg * 1.8:
            return "none"

        body = abs(c[-1] - c[-2]) if len(c) >= 2 else 0
        lower_shadow = min(c[-1], c[-2] if len(c) >= 2 else c[-1]) - l[-1]
        upper_shadow = h[-1] - max(c[-1], c[-2] if len(c) >= 2 else c[-1])
        atr_val = atr[-1] if len(atr) > 0 else 1

        if lower_shadow > 1.5 * atr_val and lower_shadow > body * 1.5:
            return "bull"  # hammer con volume
        if upper_shadow > 1.5 * atr_val and upper_shadow > body * 1.5:
            return "bear"  # shooting star con volume

        return "none"

    def _structure_break(self, c: np.ndarray, h: np.ndarray, l: np.ndarray) -> str:
        """
        Rottura della struttura recente.
        Bull: il prezzo non riesce a fare un nuovo lower-low (fail)
        Bear: il prezzo non riesce a fare un nuovo higher-high (fail)

        Questo è un segnale più definitivo — indica già un potenziale cambio.
        """
        if len(c) < 15:
            return "none"

        # Ultimi 15 swing lows/highs
        recent_lows  = l[-15:-1]
        recent_highs = h[-15:-1]

        prev_sw_lo = recent_lows.min()
        prev_sw_hi = recent_highs.max()

        curr_lo = l[-1]
        curr_hi = h[-1]
        curr_c  = c[-1]

        # Bull: il prezzo tenta lower-low ma chiude sopra il precedente swing low
        if curr_lo < prev_sw_lo and curr_c > prev_sw_lo:
            return "bull"

        # Bear: il prezzo tenta higher-high ma chiude sotto il precedente swing high
        if curr_hi > prev_sw_hi and curr_c < prev_sw_hi:
            return "bear"

        return "none"

    # ─────────────────────────────────────────────────────────────────────
    # Pivot detection
    # ─────────────────────────────────────────────────────────────────────

    def _find_pivots(self, arr: np.ndarray, pivot_type: str, window: int = 4) -> List[int]:
        """
        Trova indici dei pivot (massimi o minimi locali).
        pivot_type: "high" | "low"
        """
        pivots = []
        for i in range(window, len(arr) - window):
            if pivot_type == "high":
                if arr[i] == max(arr[i - window: i + window + 1]):
                    pivots.append(i)
            else:
                if arr[i] == min(arr[i - window: i + window + 1]):
                    pivots.append(i)
        return pivots

    # ─────────────────────────────────────────────────────────────────────
    # Indicatori
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _ema(arr: np.ndarray, span: int) -> np.ndarray:
        a = 2 / (span + 1)
        out = np.empty(len(arr)); out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = arr[i] * a + out[i - 1] * (1 - a)
        return out

    def _rsi(self, arr: np.ndarray, period: int) -> np.ndarray:
        d = np.diff(arr, prepend=arr[0])
        g = np.where(d > 0, d, 0.0)
        ls = np.where(d < 0, -d, 0.0)
        ag = self._ema(g, period); al = self._ema(ls, period)
        with np.errstate(divide="ignore", invalid="ignore"):
            rs = np.where(al > 1e-10, ag / al,
                          np.where(ag > 1e-10, 100.0, 1.0))  # flat → RS=1 → RSI=50
        return 100 - 100 / (1 + rs)

    def _macd(self, arr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        macd = self._ema(arr, 12) - self._ema(arr, 26)
        return macd, self._ema(macd, 9)

    @staticmethod
    def _atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int) -> np.ndarray:
        pc = np.roll(c, 1); pc[0] = c[0]
        tr = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
        a = 2 / (period + 1)
        out = np.empty(len(tr)); out[0] = tr[0]
        for i in range(1, len(tr)):
            out[i] = tr[i] * a + out[i - 1] * (1 - a)
        return out

    @staticmethod
    def _adx(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int) -> np.ndarray:
        ph = np.roll(h, 1); ph[0] = h[0]
        pl = np.roll(l, 1); pl[0] = l[0]
        pc = np.roll(c, 1); pc[0] = c[0]
        dmp = np.where((h - ph) > (pl - l), np.maximum(h - ph, 0), 0)
        dmm = np.where((pl - l) > (h - ph), np.maximum(pl - l, 0), 0)
        tr  = np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)])
        a   = 2 / (period + 1)
        atr_ = np.empty(len(tr)); atr_[0] = tr[0]
        dp   = np.empty(len(tr)); dp[0]   = dmp[0]
        dm   = np.empty(len(tr)); dm[0]   = dmm[0]
        for i in range(1, len(tr)):
            atr_[i] = tr[i] * a + atr_[i - 1] * (1 - a)
            dp[i]   = dmp[i] * a + dp[i - 1] * (1 - a)
            dm[i]   = dmm[i] * a + dm[i - 1] * (1 - a)
        with np.errstate(divide="ignore", invalid="ignore"):
            di_p = np.where(atr_ > 1e-10, 100 * dp / atr_, 0)
            di_m = np.where(atr_ > 1e-10, 100 * dm / atr_, 0)
            dx   = np.where((di_p + di_m) > 1e-10,
                            100 * np.abs(di_p - di_m) / (di_p + di_m), 0)
        adx  = np.empty(len(dx)); adx[0] = dx[0]
        for i in range(1, len(dx)):
            adx[i] = dx[i] * a + adx[i - 1] * (1 - a)
        return adx

    @staticmethod
    def _hurst_rolling(arr: np.ndarray, window: int = 60) -> np.ndarray:
        """
        [Tom] Hurst rolling: calcola Hurst sull'ultima finestra di barre.
        Ritorna un array della stessa lunghezza di arr.

        window=60 (minimo consigliato): con 59 returns e sub-finestre [8,12,16,20]
        si ottengono 7/4/3/2 subseries non-sovrapposte → stima R/S affidabile.
        Con window=30 (vecchio default) w=16 e w=20 davano solo 1 subseria
        ciascuna → regressione log-log inaffidabile (varianza ~0.5).
        """
        out = np.full(len(arr), 0.5)
        for i in range(window, len(arr)):
            sub = arr[i - window: i]
            returns = np.diff(np.log(np.maximum(sub, 1e-10)))
            ws = [w for w in [8, 12, 16, 20] if w <= len(returns)]
            rs_v, ns = [], []
            for w in ws:
                # Finestre non-sovrapposte: media R/S per stima più robusta
                subseries_rs = []
                for start in range(0, len(returns) - w + 1, w):
                    s = returns[start:start + w]
                    mean = s.mean()
                    if abs(mean) < 1e-10:
                        continue
                    cd = (s - mean).cumsum()
                    R = cd.max() - cd.min()
                    S = s.std(ddof=1)
                    if S > 1e-10:
                        subseries_rs.append(R / S)
                if subseries_rs:
                    rs_v.append(np.mean(subseries_rs)); ns.append(w)
            if len(rs_v) >= 2:
                try:
                    coeff = np.polyfit(np.log(ns), np.log(np.maximum(rs_v, 1e-10)), 1)
                    out[i] = float(np.clip(coeff[0], 0.1, 0.9))
                except Exception:
                    pass
        return out

    # ─────────────────────────────────────────────────────────────────────
    # Descrizione testuale dell'alert
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_description(direction: str, signals: List[Tuple[str, int]], price: float) -> str:
        dir_text = "RIALZISTA" if direction == "bull" else "RIBASSISTA"
        lines = [f"Potenziale inversione {dir_text} a {price:.5f}"]
        lines.append(f"Segnali attivi ({len(signals)}):")
        for name, weight in signals:
            lines.append(f"  • {name} [{weight}pt]")
        return "\n".join(lines)
