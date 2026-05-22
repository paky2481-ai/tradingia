"""
PairsMeanReversionSignal — implementazione completa.

Matematica (VALIDATION_PROTOCOL §1, Segnale B)
-----------------------------------------------

Step 1 — Test ADF individuale (conferma I(1)):
  ADF su log(P_a) e log(P_b) → p-value > adf_pvalue_thresh (NON stazionarie).
  Se una delle due è già stazionaria (I(0)) il pair non è cointegrato: return [].

Step 2 — Regressione di cointegrazione su log-prezzi (finestra rolling):
  log(P_a(t)) = beta(t) * log(P_b(t)) + alpha(t) + epsilon(t)
  beta_hat calcolato via OLS su finestra rolling di coint_window barre.
  MAI su tutto il dataset: farlo introduce look-ahead bias documentato in §6 regola 1.

Step 3 — Spread e ADF sui residui:
  spread(t) = log(P_a(t)) - beta_hat(t) * log(P_b(t))
  ADF sui residui → p-value < adf_pvalue_thresh (spread stazionario).

Step 4 — Half-life del mean-reversion:
  Regressione AR(1) sui residui: delta_e(t) = lambda * e(t-1) + noise
  rho_AR1 = 1 + lambda
  tau = -log(2) / log(rho_AR1)
  Se tau > max_half_life_bars: pair troppo lento → return [].

Step 5 — z-score rolling dello spread:
  mu_t   = rolling_mean(spread, zscore_window)
  sig_t  = rolling_std(spread,  zscore_window)
  z(t)   = (spread(t) - mu_t(t)) / sig_t(t)

  CRITICO: mu e sig vengono calcolati su finestre CHIUSE al giorno t
  (non shiftate: lo spread di t è una funzione di P_a(t) e P_b(t) che sono
  già chiusi; il z-score può usare spread(t) nella finestra).
  Il look-ahead bias è già evitato nella stima di beta_hat (rolling IS window).

Score:
  score_a = clip(-z / z_stop, -1, +1)
  direction_a: long  se z < -z_entry, short se z > +z_entry, flat altrimenti.
  direction_b: opposta (il pair è market-neutral per costruzione).
  confidence: |z| / z_stop, saturata a 1.

Exit signals:
  z-score scende sotto z_exit → chiusura posizione (non implementata qui:
  la logica di uscita è nel Backtester, il segnale restituisce solo lo stato
  corrente).

Look-ahead bias documentato e mitigato:
  - beta_hat: OLS solo sulla finestra coint_window PASSATA (iloc[i-W:i]).
  - z-score: rolling chiusa su barre passate + barra corrente (OK: la barra
    corrente è chiusa al momento del calcolo, e l'esecuzione è alla barra+1).
  - ADF sui residui: calcolata sulla finestra rolling (non full-sample).
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

try:
    from statsmodels.tsa.stattools import adfuller
    _STATSMODELS_OK = True
except ImportError:
    _STATSMODELS_OK = False

from strategies.signal_base import (
    ParamSpec,
    Signal,
    SignalCategory,
    SignalOutput,
    SignalScope,
)

logger = logging.getLogger("strategies.signals.pairs_mean_reversion")

# Numero minimo di barre per eseguire ADF con potenza statistica accettabile.
# MacKinnon (1994): N < 50 → elevata varianza nella distribuzione nulla.
_MIN_BARS_ADF = 50


class PairsMeanReversionSignal(Signal):
    """
    Pairs mean-reversion su spread cointegrato (VALIDATION_PROTOCOL §1, Segnale B).

    Riceve (sym_a, df_a, sym_b, df_b) e restituisce due SignalOutput (una per gamba).
    """

    signal_id       = "pairs_mean_reversion"
    label           = "Pairs Mean Reversion"
    scope           = SignalScope.PAIR
    category        = SignalCategory.MEAN_REVERSION
    default_weight  = 1.0
    default_enabled = False   # abilitato solo dopo PASS del §4

    param_specs = [
        ParamSpec(
            "z_entry", "float", 2.0, lo=1.0, hi=4.0,
            description="|z-score| soglia di ingresso",
        ),
        ParamSpec(
            "z_exit", "float", 0.5, lo=0.0, hi=2.0,
            description="|z-score| soglia di chiusura (mean reversion raggiunta)",
        ),
        ParamSpec(
            "z_stop", "float", 3.5, lo=2.0, hi=6.0,
            description="|z-score| soglia di stop loss",
        ),
        ParamSpec(
            "coint_window", "int", 252, lo=60, hi=756,
            description="Barre rolling per la stima di beta_hat (finestra IS)",
        ),
        ParamSpec(
            "zscore_window", "int", 60, lo=20, hi=252,
            description="Barre rolling per media e std del z-score",
        ),
        ParamSpec(
            "max_half_life_bars", "int", 30, lo=5, hi=120,
            description="Half-life massima accettabile (barre) per il mean-reversion",
        ),
        ParamSpec(
            "adf_pvalue_thresh", "float", 0.05, lo=0.01, hi=0.10,
            description="p-value massimo per ADF stazionarietà residui",
        ),
    ]

    # ── Implementazione compute() ──────────────────────────────────────────────

    def compute(
        self,
        data: Tuple[str, pd.DataFrame, str, pd.DataFrame],
    ) -> List[SignalOutput]:
        """
        Calcola il segnale pairs mean-reversion.

        Parameters
        ----------
        data : (sym_a, df_a, sym_b, df_b)
            Entrambi i DataFrame devono avere colonna 'close' e essere allineati
            sullo stesso DatetimeIndex (con gaps già rimossi dal chiamante).

        Returns
        -------
        [SignalOutput_a, SignalOutput_b]   — se il pair è cointegrato e tradabile.
        []                                 — se ADF, half-life o dati insufficienti.
        """
        if not _STATSMODELS_OK:
            logger.error("PairsMeanReversion: statsmodels non disponibile.")
            return []

        if not (isinstance(data, (tuple, list)) and len(data) == 4):
            logger.error("PairsMeanReversion: data deve essere (sym_a, df_a, sym_b, df_b)")
            return []

        sym_a, df_a, sym_b, df_b = data

        # Estrai e allinea le serie di close
        series_a, series_b = self._align_close(sym_a, df_a, sym_b, df_b)
        if series_a is None:
            return []

        n = len(series_a)
        W = self.coint_window   # finestra rolling IS per beta_hat

        if n < W + self.zscore_window + 10:
            logger.debug(
                "PairsMeanReversion: %s/%s: %d barre < %d minimo, skip",
                sym_a, sym_b, n, W + self.zscore_window + 10,
            )
            return []

        # Log-prezzi (stabilizza varianza, normalizza le scale)
        log_a = np.log(series_a.values.astype(float))
        log_b = np.log(series_b.values.astype(float))

        # ── Step 1: ADF individuale (conferma I(1)) ────────────────────────
        # Entrambe le serie devono essere NON stazionarie (I(1)).
        # Se una è stazionaria non c'è cointegrazione nella forma standard.
        # Usiamo l'intera history disponibile per il test individuale;
        # questo non è look-ahead: stiamo testando le proprietà stocastiche
        # della serie per decidere se costruire lo spread.
        ok_a = self._is_i1(log_a, f"{sym_a}(log)")
        ok_b = self._is_i1(log_b, f"{sym_b}(log)")
        if not (ok_a and ok_b):
            logger.debug(
                "PairsMeanReversion: %s/%s ADF individuale FAIL (ok_a=%s, ok_b=%s)",
                sym_a, sym_b, ok_a, ok_b,
            )
            return []

        # ── Step 2: Beta_hat rolling (finestra IS) ─────────────────────────
        # OLS su finestra [t-W, t) — MAI su tutto il dataset.
        # In compute() siamo all'ultimo bar: t = n-1, IS window = [n-1-W, n-1).
        # Il validate_signals.py chiama compute() barra-per-barra in modo
        # che questo coincida con la finestra "viva" al momento del segnale.
        is_window_a = log_a[n - W - 1 : n - 1]   # W barre, esclude la corrente
        is_window_b = log_b[n - W - 1 : n - 1]

        if len(is_window_a) < _MIN_BARS_ADF:
            return []

        beta_hat, alpha_hat = self._ols(is_window_b, is_window_a)
        if not np.isfinite(beta_hat) or beta_hat <= 0:
            logger.debug("PairsMeanReversion: %s/%s beta_hat non valido: %.4f", sym_a, sym_b, beta_hat)
            return []

        # ── Step 3: Spread e ADF sui residui ──────────────────────────────
        # spread calcolato sull'intera history con beta_hat stimato su IS window.
        # Questo introduce una piccola look-forward nella stima dei residui OOS,
        # ma è la metodologia standard del Backtester pairs (Vidyamurthy 2004).
        # Il validate_signals.py usa un loop rolling che ri-stima beta_hat a
        # ogni barra OOS → bias minimizzato.
        spread = log_a - beta_hat * log_b - alpha_hat   # serie completa

        # ADF sui residui dell'IS window (non dell'OOS)
        residuals_is = spread[n - W - 1 : n - 1]
        adf_pval = self._adf_pvalue(residuals_is, f"{sym_a}/{sym_b} residui")
        if adf_pval is None or adf_pval > self.adf_pvalue_thresh:
            logger.debug(
                "PairsMeanReversion: %s/%s ADF residui p=%.4f > %.4f, skip",
                sym_a, sym_b, adf_pval or 1.0, self.adf_pvalue_thresh,
            )
            return []

        # ── Step 4: Half-life AR(1) ────────────────────────────────────────
        # Modello: delta_e(t) = lambda * e(t-1) + noise
        # rho_AR1 = 1 + lambda → half_life = -log(2)/log(rho_AR1)
        half_life = self._compute_half_life(residuals_is)
        if half_life is None or half_life > self.max_half_life_bars:
            logger.debug(
                "PairsMeanReversion: %s/%s half-life %.1f > %d, skip",
                sym_a, sym_b, half_life or float("inf"), self.max_half_life_bars,
            )
            return []

        # ── Step 5: z-score rolling ────────────────────────────────────────
        # Finestra zscore_window: usa barre passate incluso il bar corrente.
        # È corretto: spread(t) è già chiuso; l'esecuzione è alla barra+1.
        spread_series = pd.Series(spread)
        roll = spread_series.rolling(window=self.zscore_window, min_periods=self.zscore_window // 2)
        mu_roll  = roll.mean()
        std_roll = roll.std(ddof=1)

        last_spread = float(spread[-1])
        last_mu     = float(mu_roll.iloc[-1])
        last_std    = float(std_roll.iloc[-1])

        if not np.isfinite(last_mu) or not np.isfinite(last_std) or last_std < 1e-12:
            logger.debug("PairsMeanReversion: %s/%s z-score non calcolabile", sym_a, sym_b)
            return []

        z = (last_spread - last_mu) / last_std

        # ── Score e direction ──────────────────────────────────────────────
        # score_a = -z / z_stop (saturato in [-1, +1])
        # z >> 0: spread sopra media → aspettiamo convergenza → short A, long B
        # z << 0: spread sotto media → aspettiamo convergenza → long A, short B
        score_a = float(np.clip(-z / self.z_stop, -1.0, 1.0))
        score_b = -score_a   # gamba opposta (market-neutral)

        if z > self.z_entry:
            dir_a, dir_b = "short", "long"
        elif z < -self.z_entry:
            dir_a, dir_b = "long", "short"
        else:
            dir_a, dir_b = "flat", "flat"

        # Confidence: |z| normalizzato rispetto a z_stop (max a 1.0)
        confidence = float(np.clip(abs(z) / self.z_stop, 0.0, 1.0))

        metadata = {
            "z_score":       round(float(z), 4),
            "beta_hat":      round(float(beta_hat), 6),
            "alpha_hat":     round(float(alpha_hat), 6),
            "half_life_bars":round(float(half_life), 1),
            "adf_pvalue":    round(float(adf_pval), 5),
            "spread_value":  round(float(last_spread), 6),
            "spread_mean":   round(float(last_mu), 6),
            "spread_std":    round(float(last_std), 6),
        }

        return [
            SignalOutput(
                symbol    = sym_a,
                score     = round(score_a, 4),
                confidence= round(confidence, 4),
                direction = dir_a,
                metadata  = metadata,
            ),
            SignalOutput(
                symbol    = sym_b,
                score     = round(score_b, 4),
                confidence= round(confidence, 4),
                direction = dir_b,
                metadata  = metadata,
            ),
        ]

    # ── Utility matematiche ────────────────────────────────────────────────────

    def _align_close(
        self,
        sym_a: str, df_a: pd.DataFrame,
        sym_b: str, df_b: pd.DataFrame,
    ) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
        """
        Estrae e allinea le serie 'close' dei due asset.
        Ritorna (None, None) se i dati sono insufficienti o invalidi.
        """
        for sym, df in ((sym_a, df_a), (sym_b, df_b)):
            if "close" not in df.columns:
                logger.error("PairsMeanReversion: %s senza colonna 'close'", sym)
                return None, None
            if df["close"].isna().all():
                logger.error("PairsMeanReversion: %s close tutto NaN", sym)
                return None, None

        # Allineamento su indice comune
        if isinstance(df_a.index, pd.DatetimeIndex) and isinstance(df_b.index, pd.DatetimeIndex):
            common = df_a.index.intersection(df_b.index)
            if len(common) < _MIN_BARS_ADF:
                logger.debug(
                    "PairsMeanReversion: %s/%s indici comuni %d < %d",
                    sym_a, sym_b, len(common), _MIN_BARS_ADF,
                )
                return None, None
            s_a = df_a.loc[common, "close"].dropna().astype(float)
            s_b = df_b.loc[common, "close"].dropna().astype(float)
        else:
            # Fallback: allineamento per posizione (entrambi già allineati dal chiamante)
            min_len = min(len(df_a), len(df_b))
            s_a = df_a["close"].iloc[:min_len].astype(float)
            s_b = df_b["close"].iloc[:min_len].astype(float)

        # Rimuovi prezzi non positivi
        valid = (s_a > 0) & (s_b > 0)
        s_a, s_b = s_a[valid], s_b[valid]

        if len(s_a) < _MIN_BARS_ADF:
            return None, None

        return s_a, s_b

    def _is_i1(self, log_prices: np.ndarray, label: str) -> bool:
        """
        Verifica che una serie sia integrata di ordine 1 (I(1)):
          - ADF sul livello → p > adf_pvalue_thresh (non stazionaria)
          - ADF sulle differenze → p < adf_pvalue_thresh (stazionaria in differenza)

        Ritorna True se entrambe le condizioni sono soddisfatte.
        """
        if len(log_prices) < _MIN_BARS_ADF:
            return False

        # ADF sul livello
        p_level = self._adf_pvalue(log_prices, f"{label} livello")
        if p_level is None:
            return False
        if p_level < self.adf_pvalue_thresh:
            # La serie è già stazionaria → non è I(1)
            logger.debug("%s: già stazionaria in livello (p=%.4f)", label, p_level)
            return False

        # ADF sulle differenze prime
        diff = np.diff(log_prices)
        if len(diff) < _MIN_BARS_ADF:
            return False
        p_diff = self._adf_pvalue(diff, f"{label} diff")
        if p_diff is None:
            return False
        if p_diff > self.adf_pvalue_thresh:
            # Anche le differenze non sono stazionarie → forse I(2)
            logger.debug("%s: differenze non stazionarie (p=%.4f)", label, p_diff)
            return False

        return True

    def _adf_pvalue(self, series: np.ndarray, label: str) -> Optional[float]:
        """
        Esegue l'ADF test (Augmented Dickey-Fuller) con selezione automatica
        dei lag via IC (information criterion 'AIC').

        Ritorna il p-value (float) oppure None in caso di errore.
        """
        if len(series) < _MIN_BARS_ADF:
            return None
        try:
            result = adfuller(series, autolag="AIC", maxlag=12)
            return float(result[1])   # result[1] = p-value
        except Exception as exc:
            logger.warning("ADF error su %s: %s", label, exc)
            return None

    def _ols(
        self,
        x: np.ndarray,
        y: np.ndarray,
    ) -> Tuple[float, float]:
        """
        OLS semplice: y = beta * x + alpha + epsilon.
        Ritorna (beta_hat, alpha_hat).
        Usa scipy.stats.linregress per efficienza.
        """
        result = scipy_stats.linregress(x, y)
        return float(result.slope), float(result.intercept)

    def _compute_half_life(self, spread: np.ndarray) -> Optional[float]:
        """
        Stima la half-life del mean-reversion via AR(1) sui residui:

            delta_e(t) = lambda * e(t-1) + noise

        OLS: y = delta_e, x = e(t-1)
        rho_AR1 = 1 + lambda
        half_life = -log(2) / log(rho_AR1)

        Ritorna None se rho_AR1 >= 1 (non mean-reverting).
        """
        if len(spread) < 3:
            return None

        e_lag   = spread[:-1]
        delta_e = spread[1:] - spread[:-1]

        # OLS semplice: delta_e = lambda * e_lag + intercept
        try:
            result = scipy_stats.linregress(e_lag, delta_e)
            lam = float(result.slope)   # lambda
        except Exception:
            return None

        rho = 1.0 + lam   # rho_AR1

        # Per mean-reversion: rho deve essere in (0, 1)
        if rho <= 0 or rho >= 1.0:
            return None

        half_life = -np.log(2.0) / np.log(rho)

        if not np.isfinite(half_life) or half_life <= 0:
            return None

        return float(half_life)
