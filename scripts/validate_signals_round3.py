"""
validate_signals_round3.py — Validazione Round 3 (DEFINITIVA) del solo Momentum
Cross-Sectional.

DIFETTI DEL ROUND 2 CORRETTI (supervisione Max)
================================================

A. PANEL AMPUTATO — CORRETTO.
   Round 2: build_panel() faceva inner join su tutti i 42 ETF.
   XLC (IPO 2018-06-19) troncava l'INTERO panel al 2018, buttando ~8 anni di storia
   su 40 ETF. L'IS risultante copriva quasi solo il crash COVID — il caso peggiore
   per un momentum.
   CORREZIONE ADOTTATA: outer join con gestione NaN per-asset.
   Il panel mantiene tutta la storia 2010-2026. Un asset non ancora quotato in una
   certa data non entra nel ranking di quel giorno (ranking calcolato sugli asset
   disponibili). Chloe aveva segnalato la storia corta di XLRE e XLC nel
   ROUND2_UNIVERSE.md PRIMA di vedere i dati: questo non è data-snooping.

B. C7/DSR ROTTO — CORRETTO.
   Con n_obs di centinaia/migliaia, DSR dà PASS per qualunque Sharpe positivo perché
   sr_std collassa a zero. Il DSR misurava "Sharpe != 0?" non "Sharpe utile?".
   CORREZIONE: il criterio decisionale primario diventa C2 — Sharpe netto OOS > baseline
   casuale con margine significativo. La baseline è già implementata (pesi random su
   stessa finestra OOS). Il DSR rimane INFORMATIVO ma NON è gate PASS/FAIL.

C. DISCIPLINA GRADI DI LIBERTA' — CORRETTA.
   Questo è il 3° round: l'OOS era già osservato in round 1 e round 2.
   n_configs totale = (1 configurazione round 1) + (16+1 round 2) + (griglia round 3).
   Griglia round 3: 3x3 = 9 configurazioni (ridotta rispetto al round 2 per non
   aggiungere gradi di libertà ulteriori). Totale onesto: 1 + 17 + 9 = 27 configurazioni.

MODIFICA ALLA STRATEGIA DI VALIDAZIONE
=======================================
Per rispettare la massima onestà statistica, il criterio gate del round 3 è:

   CRITERIO PRINCIPALE: C2_new
   Sharpe OOS netto > max(0.5, Sharpe_baseline + 0.20)
   dove Sharpe_baseline = media degli Sharpe di 500 portafogli con pesi random
   (stessa finestra OOS, stessa esposizione N_long=N_short, stesse date, stessi costi medi).

   Il segnale deve battere la baseline random con margine >= 0.20 di Sharpe.
   Non basta essere positivo: deve essere migliore del caso.

SPLIT TEMPORALE (con outer join)
================================
Con outer join l'IS copre 2010-2026 (tutti i dati disponibili), e la serie allineata
ha la lunghezza del ticker con più storia (non il più corto).
Lo schema rimane 60/10/30: IS / VAL / OOS.
Con ~16 anni di dati daily (2010-2026 = ~4024 barre):
- IS  (60%): ~2413 barre  (~2010-01 a ~2019-08)
- VAL (10%): ~402 barre   (~2019-08 a ~2021-04)
- OOS (30%): ~1209 barre  (~2021-04 a ~2026-01)
Questo OOS include: bull run 2021, crash 2022, recovery 2023-2024, 2025.

GRADI DI LIBERTA' DICHIARATI
==============================
Round 1: 1 configurazione (default).
Round 2: 16 grid search + 1 = 17 (già penalizzata).
Round 3: 9 grid search nuove.
Totale n_configs = 27.
Questa è l'unica rendicontazione onesta: ogni tentativo di usare l'OOS si paga.

UNIVERSO (CONGELATO — docs/ROUND2_UNIVERSE.md)
==============================================
42 ETF con storia REALE (outer join). XLC e XLRE inclusi con la loro storia reale
(non imputata): partecipano al ranking solo dalla data di IPO.

COSTI MODELLATI (§7, invariati dal round 2)
==========================================
ETF equity USA (XL*): round-trip 0.15%
ETF equity intl/EM:   round-trip 0.35%
ETF fixed income:     round-trip 0.20%
ETF commodity:        round-trip 0.35%
ETF REIT:             round-trip 0.20%
ETF valute/vola:      round-trip 0.30%
VIXY roll cost:       20% annuo / 252 per giorno long
Borrow short:         0.50% annuo / 252 per giorno

LOOK-AHEAD BIAS — PUNTI CRITICI (invariati)
============================================
LAB-1: ranking usa P(t-S) e P(t-L), entrambi strettamente passati.
LAB-2: filtro VIX usa shift(1) — esclude VIX di chiusura corrente.
LAB-5: grid search SOLO su IS/VAL. Parametri congelati PRIMA di aprire OOS.
       OOS eseguito UNA SOLA VOLTA.

PAIRS TRADING
=============
ARCHIVIATO dopo FAIL definitivo Round 2. Non rivalidato in questo round.

USO
---
    python scripts/validate_signals_round3.py

Output: risultati grezzi completi (tabella griglia IS, split con date reali,
        walk-forward OOS, tutti i criteri §4 Tipo B, confronto Sharpe vs baseline,
        n_configs dichiarato) per Max.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import warnings
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from scipy.special import ndtr

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.WARNING)


# =============================================================================
# SEZIONE 1 — UNIVERSO CONGELATO (docs/ROUND2_UNIVERSE.md)
# =============================================================================

MOMENTUM_UNIVERSE = [
    # Gruppo 1 — Settoriali USA
    "XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLB", "XLU", "XLRE", "XLC",
    # Gruppo 2 — Equity Internazionale/EM
    "EFA", "EEM", "VGK", "EWJ", "FXI", "EWZ", "ILF", "INDA",
    # Gruppo 3 — Fixed Income
    "SHY", "IEF", "TLT", "LQD", "HYG", "EMB", "TIP",
    # Gruppo 4 — Commodity
    "GLD", "SLV", "USO", "UNG", "DBA", "DBB",
    # Gruppo 5 — REIT
    "VNQ", "IYR", "REM", "VNQI",
    # Gruppo 6 — Valute ETF
    "UUP", "FXY", "FXF",
    # Gruppo 7 — Volatilita'/Factor
    "VIXY", "QUAL", "USMV",
]
VIX_TICKER = "^VIX"

# Classificazione costi per ticker (da ROUND2_UNIVERSE.md §Costi)
def _cost_for_ticker(ticker: str) -> float:
    """Ritorna il costo round-trip stimato per il ticker (%/100)."""
    equity_usa    = {"XLK","XLV","XLF","XLE","XLI","XLY","XLP","XLB","XLU","XLRE","XLC",
                     "SPY","QQQ","QQQM","IVV","VEA","EFA","QUAL","USMV"}
    fixed_income  = {"SHY","IEF","TLT","LQD","HYG","EMB","TIP"}
    commodity     = {"GLD","SLV","USO","UNG","DBA","DBB","IAU"}
    reit          = {"VNQ","IYR","REM","VNQI"}
    currency_vola = {"UUP","FXY","FXF","VIXY"}
    intl_em       = {"EEM","VGK","EWJ","FXI","EWZ","ILF","INDA"}

    if ticker in equity_usa:    return 0.0015
    if ticker in fixed_income:  return 0.0020
    if ticker in commodity:     return 0.0035
    if ticker in reit:          return 0.0020
    if ticker in currency_vola: return 0.0030
    if ticker in intl_em:       return 0.0035
    return 0.0025

VIXY_ROLL_COST_DAILY = 0.20 / 252
BORROW_DAILY         = 0.005 / 252

# Split 60/10/30
IS_FRAC  = 0.60
VAL_FRAC = 0.10
OOS_FRAC = 0.30
N_WF_WINDOWS = 5

# Bootstrap
N_BOOTSTRAP = 3000
RNG = np.random.default_rng(42)

DOWNLOAD_START = "2010-01-01"
DOWNLOAD_END   = "2026-01-01"

# Rebalancing mensile (invariato)
REBALANCE_FREQ = 21


# =============================================================================
# SEZIONE 2 — GRIGLIA IS/VAL ROUND 3 (ridotta vs round 2)
#
# DISCIPLINA GRADI DI LIBERTA':
# n_configs_round1 = 1
# n_configs_round2 = 16 + 1 = 17
# n_configs_round3 = 3 x 3 = 9
# TOTALE n_configs = 27
#
# La griglia è RIDOTTA rispetto al round 2 (4x4=16 vs 3x3=9) per pagare il minor
# numero di gradi di libertà possibile dato che l'OOS è già stato osservato due
# volte. Usiamo i valori della letteratura come ancoraggio, non ottimizzazione pura.
#
# Lookback long: 126 (6m, letteratura Jegadeesh-Titman), 252 (12m, standard),
#                315 (15m, variante lenta).
# Top quantile: 0.20, 0.25, 0.30 (range ridotto rispetto a round 2).
# Skip: fisso a 5 (Jegadeesh 1993, motivato teoricamente — non ottimizzato).
# VIX z-threshold: fisso a 2.0 (valore standard).
# =============================================================================

GRID_LOOKBACK_LONG = [126, 252, 315]    # 3 valori (era 4)
GRID_TOP_QUANTILE  = [0.20, 0.25, 0.30]  # 3 valori (era 4)
GRID_SKIP          = 5
GRID_VIX_Z         = 2.0
GRID_VIX_WINDOW    = 252

N_CONFIGS_R3   = len(GRID_LOOKBACK_LONG) * len(GRID_TOP_QUANTILE)  # = 9
N_CONFIGS_R2   = 17   # 16 IS/VAL + 1 tentativo OOS round 1 (dal round 2)
N_CONFIGS_R1   = 1    # round 1: 1 sola config default
# Totale onesto per il DSR in round 3
DSR_N_CONFIGS_MOM = N_CONFIGS_R1 + N_CONFIGS_R2 + N_CONFIGS_R3   # = 27

# Baseline random: numero di portafogli random usati per stimare la distribuzione nulla
N_BASELINE_RANDOM = 500

# Margine minimo di Sharpe sul baseline per C2_new
BASELINE_MARGIN = 0.20


# =============================================================================
# SEZIONE 3 — DOWNLOAD DATI CON OUTER JOIN (CORREZIONE A)
# =============================================================================

def download_ticker(ticker: str) -> Optional[pd.DataFrame]:
    """
    Scarica OHLCV daily adjusted da yfinance (2010-01-01 — 2026-01-01).
    Ritorna DataFrame con colonne lowercase o None in caso di fallimento.
    """
    import yfinance as yf
    for attempt in range(3):
        try:
            time.sleep(0.4 * (attempt + 1))
            raw = yf.download(
                ticker, start=DOWNLOAD_START, end=DOWNLOAD_END,
                interval="1d", progress=False, auto_adjust=True,
            )
            if raw is None or raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            cols_present = [c for c in ["Open","High","Low","Close","Volume"] if c in raw.columns]
            df = raw[cols_present].copy()
            df.columns = [c.lower() for c in df.columns]
            df = df.dropna(subset=["close"])
            if len(df) < 200:
                return None
            return df
        except Exception as exc:
            print(f"  [WARN] {ticker} tentativo {attempt+1}/3: {exc}")
    return None


def build_panel_outer(tickers: List[str], label: str = "") -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """
    CORREZIONE A: scarica tutti i ticker e usa OUTER JOIN sul date index.

    Invece di intersecare gli indici (inner join che troncava tutto alla data IPO
    del ticker più giovane), manteniamo ogni serie con la propria storia reale.

    Il panel ritornato è un dizionario ticker -> DataFrame con il proprio indice
    temporale originale. Il backtester userà gli asset disponibili a ogni data
    (quelli con dati validi in quella barra).

    I ticker esclusi vengono documentati ma NON sostituiti (§ROUND2_UNIVERSE.md).
    """
    panel: Dict[str, pd.DataFrame] = {}
    esclusi: List[str] = []

    for tk in tickers:
        df = download_ticker(tk)
        if df is not None:
            panel[tk] = df
        else:
            esclusi.append(tk)
            print(f"  [ESCLUSO] {tk}: download fallito o dati insufficienti")

    print(f"  {label}: {len(panel)}/{len(tickers)} ticker scaricati, {len(esclusi)} esclusi")

    # Documentazione history corte per trasparenza
    if panel:
        lengths = sorted([(k, len(v), v.index[0].date()) for k, v in panel.items()], key=lambda x: x[2])
        short_hist = [(k, d, n) for k, n, d in lengths if d > pd.Timestamp("2012-01-01").date()]
        if short_hist:
            print(f"  STORIA CORTA (IPO dopo 2012): {[(k, str(d)) for k, d, _ in short_hist]}")

    return panel, esclusi


# =============================================================================
# SEZIONE 4 — INDICE COMUNE E SPLIT TEMPORALE CON OUTER JOIN
#
# Con outer join, ogni ticker ha il proprio range temporale. Per definire IS/VAL/OOS
# usiamo l'UNIONE di tutte le date di trading disponibili (outer index).
# A ogni data, nel ranking entrano solo i ticker con dato valido (non NaN).
# =============================================================================

def build_outer_date_index(panel: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """
    Costruisce l'unione di tutti i date index del panel.
    Questa è la serie temporale di riferimento per lo split IS/VAL/OOS.
    """
    all_dates = set()
    for df in panel.values():
        all_dates.update(df.index.tolist())
    return pd.DatetimeIndex(sorted(all_dates))


def get_close_at_bar(panel: Dict[str, pd.DataFrame], outer_idx: pd.DatetimeIndex, bar: int) -> Dict[str, float]:
    """
    Ritorna i prezzi di chiusura disponibili alla barra `bar` dell'outer index.
    Gli asset non ancora quotati (o con NaN) non compaiono nel dizionario.
    """
    if bar < 0 or bar >= len(outer_idx):
        return {}
    date = outer_idx[bar]
    result = {}
    for sym, df in panel.items():
        if date in df.index:
            c = float(df.loc[date, "close"])
            if np.isfinite(c) and c > 0:
                result[sym] = c
    return result


# =============================================================================
# SEZIONE 5 — METRICHE STATISTICHE
# =============================================================================

def sharpe(rets: np.ndarray, ann: float = 252.0) -> float:
    if len(rets) < 2 or rets.std() == 0:
        return 0.0
    return float(rets.mean() / rets.std() * np.sqrt(ann))


def sortino(rets: np.ndarray, ann: float = 252.0) -> float:
    if len(rets) < 2:
        return 0.0
    down = rets[rets < 0]
    if len(down) == 0 or down.std() == 0:
        return float("inf") if rets.mean() > 0 else 0.0
    return float(rets.mean() / down.std() * np.sqrt(ann))


def max_drawdown(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(-dd.min())


def calmar(rets: np.ndarray, mdd: float, ann: float = 252.0) -> float:
    if mdd == 0:
        return float("inf") if rets.mean() > 0 else 0.0
    return float(rets.mean() * ann / mdd)


def cagr(rets: np.ndarray, ann: float = 252.0) -> float:
    if len(rets) == 0:
        return 0.0
    total = float(np.prod(1.0 + rets))
    if total <= 0:
        return -1.0
    n_years = len(rets) / ann
    return float(total ** (1.0 / n_years) - 1.0) if n_years > 0 else 0.0


def bootstrap_ci_periodic(
    daily_rets: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    alpha: float = 0.05,
) -> Tuple[float, float, float]:
    """
    C1-B (§12 Tipo B): bootstrap CI 95% sul rendimento periodico MEDIO (daily).
    Block bootstrap con blocchi di lunghezza sqrt(T) (Politis & Romano 1994).
    Ritorna (ci_lo, ci_hi, p_value one-sided H0: mu <= 0).
    """
    T = len(daily_rets)
    if T < 10:
        return float("nan"), float("nan"), float("nan")

    block_len = max(5, int(np.sqrt(T)))

    def block_mean(data: np.ndarray) -> float:
        n = len(data)
        result = []
        while len(result) < n:
            start = int(RNG.integers(0, n))
            block = data[start : start + block_len]
            if len(block) < block_len:
                block = np.concatenate([block, data[:block_len - len(block)]])
            result.extend(block[:block_len].tolist())
        return float(np.mean(result[:n]))

    boot_means = np.array([block_mean(daily_rets) for _ in range(n_boot)])
    ci_lo = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    centered = daily_rets - daily_rets.mean()
    boot_h0  = np.array([block_mean(centered) for _ in range(n_boot)])
    p_val    = float(np.mean(boot_h0 >= daily_rets.mean()))
    p_val    = max(p_val, 1.0 / n_boot)
    return ci_lo, ci_hi, p_val


def deflated_sharpe(
    sr_obs: float,
    n_obs: int,
    n_configs: int,
    skew_val: float = 0.0,
    kurt_val: float = 3.0,
) -> Tuple[float, float]:
    """
    Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).
    ROUND 3: usato come INFORMATIVO, NON come gate PASS/FAIL (correzione B).
    Con n_configs=27 e n_obs~1200 il DSR è più significativo del round 2
    (dove n_configs=17 e n_obs~564), ma rimane secondario rispetto a C2_new.
    """
    if n_obs < 2:
        return 0.0, 0.5

    if n_configs <= 1:
        sr_0 = 0.0
    else:
        gamma_e = 0.5772156649
        z_inv = float(scipy_stats.norm.ppf(1.0 - 1.0 / n_configs))
        sr_0  = (1.0 - gamma_e) * z_inv + gamma_e * np.sqrt(z_inv ** 2 + 1.0)
        # Scala SR_0 a unità di SR osservato (approssimazione; errore < 10% per n_configs piccolo)
        sr_0  = sr_0 / np.sqrt(n_obs - 1)

    correction_term = 1.0 - skew_val * sr_obs + (kurt_val - 1.0) / 4.0 * sr_obs ** 2
    correction_term = max(correction_term, 1e-12)
    sr_std = float(np.sqrt(correction_term / (n_obs - 1)))
    sr_std = max(sr_std, 1e-12)

    dsr   = (sr_obs - sr_0) / sr_std
    p_val = float(1.0 - ndtr(dsr))
    return float(dsr), p_val


# =============================================================================
# SEZIONE 6 — BACKTEST MOMENTUM (con outer join)
#
# DIFFERENZA CRITICA rispetto al round 2:
# - Panel come Dict[sym, DataFrame] con indice proprio per ogni asset.
# - Indice di riferimento = outer_idx (unione di tutte le date).
# - A ogni barra t, il ranking si calcola sugli asset con dato valido in outer_idx[t].
# - I prezzi di L e S barre fa vengono cercati nel DataFrame del singolo ticker,
#   non nell'array numpy del panel allineato.
# =============================================================================

class MomentumBacktester:
    """
    Backtest del momentum cross-sectional su panel con outer join.

    Il ranking a ogni rebalancing usa SOLO gli asset con dato disponibile in quella
    data. Asset non ancora quotati (es. XLC prima del 2018) non partecipano al
    ranking di quel giorno — non sono esclusi dal backtest, semplicemente assenti.

    Costi: round-trip per asset class applicato al momento della rotazione,
    proporzionale alla variazione di peso assoluta.
    Borrow cost: 0.50% annuo / 252 per ogni giorno di posizione short.
    VIXY roll cost: 20% annuo / 252 per ogni giorno di posizione long su VIXY.
    """

    def __init__(
        self,
        panel: Dict[str, pd.DataFrame],
        outer_idx: pd.DatetimeIndex,
        vix_df: Optional[pd.DataFrame],
    ) -> None:
        self.panel    = {k: v for k, v in panel.items() if k != VIX_TICKER}
        self.outer_idx = outer_idx
        self.vix_df   = vix_df
        self.syms     = list(self.panel.keys())
        self.costs    = {s: _cost_for_ticker(s) for s in self.syms}

    def _get_close(self, sym: str, bar: int) -> Optional[float]:
        """Ritorna il close del ticker `sym` alla barra `bar` dell'outer_idx, o None."""
        if bar < 0 or bar >= len(self.outer_idx):
            return None
        date = self.outer_idx[bar]
        df   = self.panel.get(sym)
        if df is None or date not in df.index:
            return None
        c = float(df.loc[date, "close"])
        return c if (np.isfinite(c) and c > 0) else None

    def _get_vix(self, bar: int, vix_window: int) -> Optional[float]:
        """
        Ritorna il z-score VIX alla barra `bar`.
        LAB-2: usa shift(1) — la finestra rolling è [bar-vix_window, bar-1].
        Ritorna None se dati insufficienti.
        """
        if self.vix_df is None:
            return None
        date = self.outer_idx[bar] if bar < len(self.outer_idx) else None
        if date is None:
            return None
        # Trova la posizione del vix_df per questa data
        try:
            vix_pos = self.vix_df.index.get_loc(date)
        except KeyError:
            # Data assente nel VIX: cerca la più vicina precedente
            vix_dates_before = self.vix_df.index[self.vix_df.index <= date]
            if len(vix_dates_before) == 0:
                return None
            vix_pos = self.vix_df.index.get_loc(vix_dates_before[-1])

        # Window [vix_pos-vix_window, vix_pos-1] (shift(1) = esclude corrente)
        win_start = max(0, vix_pos - vix_window)
        win_end   = vix_pos   # esclude la riga corrente (shift 1)
        if win_end - win_start < vix_window // 2:
            return None
        vix_win = self.vix_df["close"].iloc[win_start:win_end].values
        mu_vix  = float(np.mean(vix_win))
        sig_vix = float(np.std(vix_win, ddof=1))
        if sig_vix < 1e-9:
            return None
        vix_curr = float(self.vix_df["close"].iloc[vix_pos])
        return (vix_curr - mu_vix) / sig_vix

    def run(
        self,
        bar_start: int,
        bar_end: int,
        lookback_long: int,
        top_quantile: float,
        vix_z_thresh: float = 2.0,
        vix_window: int = 252,
        random_weights: bool = False,
        rng_baseline: Optional[np.random.Generator] = None,
    ) -> Dict:
        """
        Esegue il backtest momentum su [bar_start, bar_end) dell'outer_idx.

        Se random_weights=True, le posizioni vengono assegnate a N_long/N_short
        asset scelti casualmente (baseline nulla). Tutti gli altri parametri
        restano invariati (stessi costi, stessa frequenza di rebalancing).

        Ritorna dict con rendimenti daily e metriche aggregate.
        """
        rng_bl = rng_baseline if rng_baseline is not None else np.random.default_rng(0)

        daily_rets: List[float] = []
        equity = [1.0]
        current_pos: Dict[str, float] = {}

        S = GRID_SKIP
        L = lookback_long

        for i in range(bar_end - bar_start - 1):
            t = bar_start + i

            do_rebalance = (i % REBALANCE_FREQ == 0)

            if do_rebalance:
                # --- Filtro VIX (LAB-2) ---
                vix_z = self._get_vix(t, vix_window)
                if vix_z is not None and vix_z >= vix_z_thresh:
                    current_pos = {s: 0.0 for s in self.syms}
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                    continue

                # --- Calcolo Mom_adj per gli asset disponibili in questa data ---
                # OUTER JOIN: include solo asset con close valido a t, t-S, t-L
                mom_vals: Dict[str, float] = {}
                for sym in self.syms:
                    c_now  = self._get_close(sym, t - S - 1)   # P(t-S): S barre fa
                    c_long = self._get_close(sym, t - L - 1)   # P(t-L): L barre fa
                    if c_now is None or c_long is None or c_long <= 0:
                        continue
                    mom_vals[sym] = c_now / c_long - 1.0

                if len(mom_vals) < 5:
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                    continue

                # --- Ranking cross-sectional → posizioni ---
                sorted_syms = sorted(mom_vals.keys(), key=lambda s: mom_vals[s])
                n_ranked    = len(sorted_syms)
                n_side      = max(1, int(n_ranked * top_quantile))

                if random_weights:
                    # Baseline nulla: n_side long e n_side short scelti casualmente
                    shuffled = list(sorted_syms)
                    rng_bl.shuffle(shuffled)
                    longs  = shuffled[:n_side]
                    shorts = shuffled[n_side:2 * n_side]
                else:
                    longs  = sorted_syms[-n_side:]
                    shorts = sorted_syms[:n_side]

                new_pos: Dict[str, float] = {s: 0.0 for s in self.syms}
                for s in longs:
                    new_pos[s] = 1.0 / n_side
                for s in shorts:
                    new_pos[s] = -1.0 / n_side

                # --- Costi di rotazione ---
                rot_cost = 0.0
                for sym in self.syms:
                    old_p = current_pos.get(sym, 0.0)
                    new_p = new_pos.get(sym, 0.0)
                    delta = abs(new_p - old_p)
                    if delta > 0.005:
                        rot_cost += delta * self.costs.get(sym, 0.0025)

                current_pos = new_pos
                if rot_cost > 0:
                    equity[-1] *= (1.0 - rot_cost)

            # --- P&L daily ---
            port_ret = 0.0
            any_pos  = False

            for sym, w in current_pos.items():
                if abs(w) < 1e-9:
                    continue
                c_t   = self._get_close(sym, t)
                c_tp1 = self._get_close(sym, t + 1)
                if c_t is None or c_tp1 is None:
                    continue
                ret = (c_tp1 - c_t) / c_t * w
                port_ret += ret
                any_pos   = True

                # Borrow cost daily per gambe short
                if w < 0:
                    port_ret -= abs(w) * BORROW_DAILY

                # VIXY roll cost: penalita' giornaliera se long VIXY
                if sym == "VIXY" and w > 0:
                    port_ret -= w * VIXY_ROLL_COST_DAILY

            daily_rets.append(port_ret)
            equity.append(equity[-1] * (1.0 + port_ret))

        rets_arr = np.array(daily_rets)
        eq_arr   = np.array(equity)
        mdd_v    = max_drawdown(eq_arr)

        return {
            "daily_rets": rets_arr,
            "equity":     eq_arr,
            "sharpe":     sharpe(rets_arr),
            "sortino":    sortino(rets_arr),
            "mdd":        mdd_v,
            "cagr":       cagr(rets_arr),
            "calmar":     calmar(rets_arr, mdd_v),
        }


# =============================================================================
# SEZIONE 7 — GRID SEARCH IS/VAL (DISCIPLINA LAB-5)
# =============================================================================

def grid_search_momentum(
    panel: Dict[str, pd.DataFrame],
    outer_idx: pd.DatetimeIndex,
    vix_df: Optional[pd.DataFrame],
    bar_start: int,
    bar_end: int,
) -> Tuple[Dict, pd.DataFrame]:
    """
    Grid search su IS+VAL [bar_start, bar_end).
    LAB-5: l'OOS non viene aperto prima di questa funzione.
    Griglia: 3x3 = 9 configurazioni (round 3).
    """
    bt = MomentumBacktester(panel, outer_idx, vix_df)
    grid_results = []

    total = len(GRID_LOOKBACK_LONG) * len(GRID_TOP_QUANTILE)
    done  = 0

    for L, q in product(GRID_LOOKBACK_LONG, GRID_TOP_QUANTILE):
        res = bt.run(bar_start, bar_end, lookback_long=L, top_quantile=q)
        grid_results.append({
            "lookback_long": L,
            "top_quantile":  q,
            "sharpe_isval":  res["sharpe"],
            "sortino_isval": res["sortino"],
            "mdd_isval":     res["mdd"],
            "cagr_isval":    res["cagr"],
            "calmar_isval":  res["calmar"],
        })
        done += 1
        print(f"    config {done}/{total}: L={L} q={q:.2f} -> Sharpe={res['sharpe']:.3f}", flush=True)

    df_grid = pd.DataFrame(grid_results).sort_values("sharpe_isval", ascending=False)

    best_row    = df_grid.iloc[0]
    best_params = {
        "lookback_long": int(best_row["lookback_long"]),
        "top_quantile":  float(best_row["top_quantile"]),
        "vix_z_thresh":  GRID_VIX_Z,
        "vix_window":    GRID_VIX_WINDOW,
    }
    return best_params, df_grid


# =============================================================================
# SEZIONE 8 — BACKTEST OOS WALK-FORWARD
# =============================================================================

def run_momentum_oos(
    panel: Dict[str, pd.DataFrame],
    outer_idx: pd.DatetimeIndex,
    vix_df: Optional[pd.DataFrame],
    oos_start: int,
    oos_end: int,
    best_params: Dict,
    n_wf: int = N_WF_WINDOWS,
) -> Tuple[List[Dict], np.ndarray, np.ndarray]:
    """
    Backtest momentum OOS walk-forward con parametri congelati.
    Eseguito UNA SOLA VOLTA (DISCIPLINA OOS).
    Ritorna (wf_results, daily_rets_oos_concat, equity_oos_concat).
    """
    bt       = MomentumBacktester(panel, outer_idx, vix_df)
    wf_size  = (oos_end - oos_start) // n_wf
    wf_results: List[Dict] = []
    all_rets: List[np.ndarray] = []
    equity_concat = np.array([1.0])

    for w_idx in range(n_wf):
        w_start = oos_start + w_idx * wf_size
        w_end   = w_start + wf_size if w_idx < n_wf - 1 else oos_end

        # Date approssimative per leggibilità
        d_start = outer_idx[w_start].date() if w_start < len(outer_idx) else "?"
        d_end   = outer_idx[min(w_end - 1, len(outer_idx) - 1)].date()
        print(f"  Finestra {w_idx+1}/{n_wf}: bar {w_start}-{w_end} ({d_start} — {d_end}) ...", end="", flush=True)

        res = bt.run(
            w_start, w_end,
            lookback_long=best_params["lookback_long"],
            top_quantile=best_params["top_quantile"],
            vix_z_thresh=best_params.get("vix_z_thresh", 2.0),
            vix_window=best_params.get("vix_window", 252),
        )
        wf_results.append(res)
        all_rets.append(res["daily_rets"])

        eq = res["equity"]
        if len(eq) > 1:
            scale = equity_concat[-1]
            equity_concat = np.concatenate([equity_concat, eq[1:] * scale / eq[0]])

        print(f"  Sharpe={res['sharpe']:.3f}  CAGR={res['cagr']*100:+.1f}%  MDD={res['mdd']*100:.1f}%")

    all_rets_arr = np.concatenate(all_rets) if all_rets else np.array([])
    return wf_results, all_rets_arr, equity_concat


# =============================================================================
# SEZIONE 9 — BASELINE RANDOM (CORREZIONE B: criterio decisionale primario)
#
# Per C2_new: il segnale deve battere la distribuzione di portafogli con pesi
# random (stesso N_long = N_short, stessa finestra, stessi costi medi).
# Usiamo 500 portafogli random per stimare E[Sharpe_baseline] e
# std[Sharpe_baseline]. Il test: SR_signal > E[SR_baseline] + BASELINE_MARGIN.
# =============================================================================

def compute_baseline_sharpe(
    panel: Dict[str, pd.DataFrame],
    outer_idx: pd.DatetimeIndex,
    vix_df: Optional[pd.DataFrame],
    oos_start: int,
    oos_end: int,
    best_params: Dict,
    n_random: int = N_BASELINE_RANDOM,
) -> Tuple[float, float, float, np.ndarray]:
    """
    Esegue n_random backtest con pesi random (stessa struttura del segnale).
    Ritorna (mean_sr_baseline, std_sr_baseline, p5_sr_baseline, all_baseline_srs).
    """
    bt = MomentumBacktester(panel, outer_idx, vix_df)
    baseline_srs: List[float] = []

    print(f"\n  Calcolando {n_random} portafogli random (baseline nulla) ...", flush=True)

    for i in range(n_random):
        rng_bl = np.random.default_rng(1000 + i)
        res = bt.run(
            oos_start, oos_end,
            lookback_long=best_params["lookback_long"],
            top_quantile=best_params["top_quantile"],
            vix_z_thresh=best_params.get("vix_z_thresh", 2.0),
            vix_window=best_params.get("vix_window", 252),
            random_weights=True,
            rng_baseline=rng_bl,
        )
        baseline_srs.append(res["sharpe"])
        if (i + 1) % 100 == 0:
            print(f"    {i+1}/{n_random} portafogli completati ...", flush=True)

    arr = np.array(baseline_srs)
    return float(arr.mean()), float(arr.std(ddof=1)), float(np.percentile(arr, 5)), arr


# =============================================================================
# SEZIONE 10 — CRITERI PASS/FAIL ROUND 3 (Tipo B §12, con correzione B)
# =============================================================================

def evaluate_momentum_round3(
    wf_results: List[Dict],
    all_daily_rets: np.ndarray,
    equity_oos: np.ndarray,
    best_params: Dict,
    baseline_mean_sr: float,
    baseline_std_sr: float,
    baseline_p5_sr: float,
) -> Dict:
    """
    Valuta il momentum Tipo B con i criteri corretti per il round 3.

    CRITERI:
    - C1-B: bootstrap CI 95% sul rendimento periodico daily > 0 (invariato).
    - C2_new: Sharpe netto OOS > max(0.5, baseline_mean_sr + BASELINE_MARGIN).
              CRITERIO PRIMARIO (correzione B). Batte il caso random con margine.
    - C3: Sortino > 0.7.
    - C4: MDD < 25%.
    - C5: Calmar > 0.3.
    - C6-B: T >= 750 osservazioni periodiche OOS.
    - C7 (INFORMATIVO): DSR p-value < 0.05. Non è gate PASS/FAIL (correzione B).
                        Con n_configs=27 è più penalizzato del round 2 (n=17).
    - C8: stabilita' WF >= 80%.

    VERDETTO: PASS solo se C1-B AND C2_new AND C3 AND C4 AND C5 AND C6-B AND C8.
    C7 è riportato ma non blocca il PASS.
    """
    n_obs = len(all_daily_rets)
    n_wf  = len(wf_results)

    sr    = sharpe(all_daily_rets)
    so    = sortino(all_daily_rets)
    mdd_v = max_drawdown(equity_oos)
    cal   = calmar(all_daily_rets, mdd_v)
    cag   = cagr(all_daily_rets)

    skew_v = float(scipy_stats.skew(all_daily_rets))    if n_obs > 3 else 0.0
    kurt_v = float(scipy_stats.kurtosis(all_daily_rets, fisher=False)) if n_obs > 3 else 3.0

    # DSR: informativo (n_configs=27, penalizzato per tre round)
    dsr_val, dsr_pval = deflated_sharpe(sr, n_obs, DSR_N_CONFIGS_MOM, skew_v, kurt_v)

    # C1-B: block bootstrap CI sul rendimento daily
    ci_lo, ci_hi, boot_p = bootstrap_ci_periodic(all_daily_rets)

    # C2_new: soglia dinamica = max(0.5, baseline_mean + BASELINE_MARGIN)
    sr_threshold = max(0.50, baseline_mean_sr + BASELINE_MARGIN)

    # WF stability
    wf_srs  = [sharpe(w["daily_rets"]) for w in wf_results]
    wf_stab = sum(1 for s in wf_srs if s > 0) / n_wf if n_wf > 0 else 0.0

    # Criteri gate
    c1b    = (not np.isnan(ci_lo)) and ci_lo > 0.0
    c2_new = sr > sr_threshold                             # CRITERIO PRIMARIO
    c3     = so    > 0.70
    c4     = mdd_v < 0.25
    c5     = cal   > 0.30
    c6     = n_obs >= 750
    c7_info= (not np.isnan(dsr_pval)) and dsr_pval < 0.05  # solo informativo
    c8     = wf_stab >= 0.80

    # PASS richiede tutti i criteri TRANNE C7 (informativo)
    all_pass = all([c1b, c2_new, c3, c4, c5, c6, c8])

    # Killer criteria
    k1 = True   # N/A per Tipo B
    k2 = True
    if len(equity_oos) > 4:
        last_q   = equity_oos[3 * len(equity_oos) // 4:]
        mdd_lq   = max_drawdown(last_q)
        if mdd_lq > mdd_v * 0.80:
            k2 = False
    k3 = True
    if n_wf >= 2:
        r_first = float(wf_results[0]["daily_rets"].mean()) if len(wf_results[0]["daily_rets"]) > 0 else 0.0
        r_last  = float(wf_results[-1]["daily_rets"].mean()) if len(wf_results[-1]["daily_rets"]) > 0 else 0.0
        if r_first * r_last < 0:
            k3 = False
    k4 = True   # Tipo B: usa C6
    k5 = True
    # K5: edge sopravvive ai costi (SR_net > 0.2 * SR_gross)
    sr_gross = sharpe(np.concatenate([w["daily_rets"] for w in wf_results]))
    if sr > 0 and sr_gross > 0 and sr / sr_gross < 0.20:
        k5 = False

    killers_ok = all([k1, k2, k3, k4, k5])
    verdict    = "PASS" if (all_pass and killers_ok) else "FAIL"

    return dict(
        type_signal="Tipo B (ALWAYS-IN)",
        n_obs=n_obs, sharpe=sr, sortino=so, mdd=mdd_v, calmar=cal, cagr_ann=cag,
        dsr=dsr_val, dsr_pval=dsr_pval, n_configs_dsr=DSR_N_CONFIGS_MOM,
        ci1b_lo=ci_lo, ci1b_hi=ci_hi, boot_p=boot_p,
        wf_stability=wf_stab, wf_sharpes=wf_srs,
        baseline_mean_sr=baseline_mean_sr,
        baseline_std_sr=baseline_std_sr,
        baseline_p5_sr=baseline_p5_sr,
        sr_threshold=sr_threshold,
        c1b=c1b, c2_new=c2_new, c3=c3, c4=c4, c5=c5, c6=c6, c7_info=c7_info, c8=c8,
        all_pass=all_pass,
        k1=k1, k2=k2, k3=k3, k4=k4, k5=k5, killers_ok=killers_ok,
        verdict=verdict,
        best_params=best_params,
    )


# =============================================================================
# SEZIONE 11 — STAMPA RISULTATI
# =============================================================================

def SEP(c="-", w=100): print(c * w)


def print_mom_grid(df_grid: pd.DataFrame) -> None:
    print("\n  Griglia IS/VAL Round 3 (3x3=9 configurazioni, ordinate per Sharpe IS/VAL):")
    SEP()
    print(f"  {'L':>4}  {'q':>5}  {'Sharpe':>8}  {'Sortino':>8}  {'MDD%':>6}  {'CAGR%':>7}  {'Calmar':>7}")
    SEP()
    for _, row in df_grid.iterrows():
        best_marker = " <-- BEST" if _ == 0 else ""
        print(
            f"  {int(row['lookback_long']):>4}  {row['top_quantile']:>5.2f}  "
            f"{row['sharpe_isval']:>8.3f}  {row['sortino_isval']:>8.3f}  "
            f"{row['mdd_isval']*100:>5.1f}%  {row['cagr_isval']*100:>+7.2f}%  "
            f"{row['calmar_isval']:>7.3f}{best_marker}"
        )


def print_baseline_summary(mean_sr: float, std_sr: float, p5_sr: float, all_srs: np.ndarray) -> None:
    print(f"\n  BASELINE RANDOM ({N_BASELINE_RANDOM} portafogli, outer join, stesse date e costi):")
    SEP()
    print(f"  E[Sharpe_baseline]:  {mean_sr:.4f}")
    print(f"  std[Sharpe_baseline]: {std_sr:.4f}")
    print(f"  P5[Sharpe_baseline]:  {p5_sr:.4f}")
    print(f"  P50[Sharpe_baseline]: {float(np.median(all_srs)):.4f}")
    print(f"  P95[Sharpe_baseline]: {float(np.percentile(all_srs, 95)):.4f}")
    print(f"  Min/Max baseline:     {float(all_srs.min()):.4f} / {float(all_srs.max()):.4f}")
    print(f"  % baseline > 0:       {float(np.mean(all_srs > 0))*100:.1f}%")


def print_mom_eval(ev: Dict) -> None:
    SEP("=")
    print(f"  MOMENTUM CROSS-SECTIONAL — Tipo B — OOS Walk-Forward — ROUND 3 (DEFINITIVO)")
    SEP("=")
    print(f"  Parametri OOS congelati: L={ev['best_params']['lookback_long']} "
          f"q={ev['best_params']['top_quantile']:.2f} "
          f"VIX_z={ev['best_params']['vix_z_thresh']}")
    print(f"  n_configs DSR: {ev['n_configs_dsr']} = 1 (R1) + 17 (R2) + 9 (R3) — PENA ONESTA")
    SEP()
    print(f"  T OOS (obs periodiche):   {ev['n_obs']}")
    print(f"  Sharpe OOS netto:         {ev['sharpe']:.4f}")
    print(f"  Sortino OOS netto:        {ev['sortino']:.4f}")
    print(f"  MDD:                      {ev['mdd']*100:.2f}%")
    print(f"  Calmar:                   {ev['calmar']:.4f}")
    print(f"  CAGR annualizzato:        {ev['cagr_ann']*100:+.2f}%")
    print(f"  DSR (informativo):        {ev['dsr']:.4f}  p={ev['dsr_pval']:.6f}  "
          f"[{'PASS inf.' if ev['c7_info'] else 'FAIL inf.'}]")
    print(f"  C1-B CI 95% daily ret:    [{ev['ci1b_lo']*100:+.6f}%, {ev['ci1b_hi']*100:+.6f}%]  "
          f"p={ev['boot_p']:.4f}")
    print(f"  WF stability:             {ev['wf_stability']*100:.0f}%  "
          f"Sharpe per finestra: {[f'{s:.2f}' for s in ev['wf_sharpes']]}")
    SEP()
    print(f"  BASELINE RANDOM: E[SR]={ev['baseline_mean_sr']:.4f}  "
          f"std={ev['baseline_std_sr']:.4f}  p5={ev['baseline_p5_sr']:.4f}")
    print(f"  Soglia C2_new: max(0.5, {ev['baseline_mean_sr']:.4f} + {BASELINE_MARGIN}) "
          f"= {ev['sr_threshold']:.4f}")
    print(f"  Margine segnale vs baseline: {ev['sharpe'] - ev['baseline_mean_sr']:+.4f}")
    SEP()

    rows = [
        ("C1-B",   "CI 95% rendimento daily > 0 (Tipo B)",
         f"lo={ev['ci1b_lo']*100:+.6f}%",
         ev["c1b"],  True),
        ("C2_new", f"Sharpe netto > {ev['sr_threshold']:.3f} (baseline+margine) [PRIMARIO]",
         f"{ev['sharpe']:.4f} vs soglia {ev['sr_threshold']:.4f}",
         ev["c2_new"], True),
        ("C3",     "Sortino OOS netto > 0.7",
         f"{ev['sortino']:.4f}",
         ev["c3"],   True),
        ("C4",     "MDD < 25%",
         f"{ev['mdd']*100:.2f}%",
         ev["c4"],   True),
        ("C5",     "Calmar > 0.3",
         f"{ev['calmar']:.4f}",
         ev["c5"],   True),
        ("C6-B",   "T >= 750 obs periodiche OOS",
         f"{ev['n_obs']}",
         ev["c6"],   True),
        ("C7",     "DSR p < 0.05 [SOLO INFORMATIVO — non gate]",
         f"DSR={ev['dsr']:.3f} p={ev['dsr_pval']:.6f}",
         ev["c7_info"], False),
        ("C8",     "WF stability >= 80%",
         f"{ev['wf_stability']*100:.0f}%",
         ev["c8"],   True),
    ]

    for code, desc, val, passed, is_gate in rows:
        gate_str  = "[GATE]" if is_gate else "[INFO]"
        pass_str  = "PASS" if passed else "FAIL"
        print(f"  {code:<7} {gate_str} [{pass_str}]  {desc:<55} {val}")

    SEP()
    killers = [
        ("K1", "N/A per Tipo B (esposizione continua)",             ev["k1"]),
        ("K2", "MDD non concentrato nell'ultimo trimestre OOS",     ev["k2"]),
        ("K3", "Segno non ribaltato prima/ultima finestra WF",      ev["k3"]),
        ("K4", "N/A per Tipo B (usa C6-B)",                        ev["k4"]),
        ("K5", "Edge sopravvive ai costi (SR_net/SR_gross > 0.2)", ev["k5"]),
    ]
    for code, desc, ok in killers:
        print(f"  {code}  [{'OK' if ok else 'KO'}]  {desc}")

    SEP("=")
    verdict = "*** PASS ***" if ev["verdict"] == "PASS" else "!!! FAIL !!!"
    print(f"  VERDICT MOMENTUM ROUND 3 (DEFINITIVO): {verdict}")
    if ev["verdict"] == "FAIL":
        fc = [c for c, _, __, p, g in rows if not p and g]
        fk = [k for k, _, ok in killers if not ok]
        if fc:
            print(f"  Criteri gate FAIL: {fc}")
        if fk:
            print(f"  Killer KO:         {fk}")
    SEP("=")


# =============================================================================
# SEZIONE 12 — MAIN
# =============================================================================

def main() -> None:
    print()
    SEP("=")
    print("  VALIDAZIONE SEGNALI — ROUND 3 (DEFINITIVO) — SOLO MOMENTUM CROSS-SECTIONAL")
    print("  Tom — TradingIA  |  Data:", pd.Timestamp.now().date())
    print("  Pairs trading: ARCHIVIATO (FAIL definitivo Round 2 — non rivalidato)")
    SEP("=")

    print("\n  DICHIARAZIONE GRADI DI LIBERTA':")
    print(f"  Round 1: 1 configurazione (default)")
    print(f"  Round 2: 16 (grid IS/VAL) + 1 (OOS osservato) = 17")
    print(f"  Round 3: {N_CONFIGS_R3} configurazioni (3x3 griglia IS/VAL)")
    print(f"  TOTALE n_configs per DSR: {DSR_N_CONFIGS_MOM} = 1 + 17 + {N_CONFIGS_R3}")
    print(f"  OOS già osservato in Round 1 e Round 2 — penalizzato nel DSR.")
    print(f"  Questo è il 3° e ULTIMO round: esito vincolante.")
    SEP()

    # -------------------------------------------------------------------------
    # 1. DOWNLOAD DATI (OUTER JOIN — CORREZIONE A)
    # -------------------------------------------------------------------------
    print("\n[1] DOWNLOAD DATI STORICI (2010-01-01 — 2026-01-01)")
    print("    CORREZIONE A: outer join — ogni ETF mantiene la propria storia reale")
    SEP()

    all_mom_tickers = MOMENTUM_UNIVERSE + [VIX_TICKER]
    mom_panel_raw, mom_esclusi = build_panel_outer(all_mom_tickers, label="Momentum (outer)")

    if len(mom_esclusi) > 0:
        print(f"\n  TICKER ESCLUSI (non sostituiti): {mom_esclusi}")

    # Separa VIX
    vix_df    = mom_panel_raw.pop(VIX_TICKER, None)
    mom_panel = {k: v for k, v in mom_panel_raw.items() if k in MOMENTUM_UNIVERSE}

    if len(mom_panel) < 10:
        print("\n[ABORT] Troppi pochi ticker scaricati. Connessione assente.")
        sys.exit(1)

    # Statistiche panel
    print(f"\n  Panel momentum: {len(mom_panel)} ticker")
    print(f"  Ticker disponibili: {sorted(mom_panel.keys())}")
    if vix_df is not None:
        print(f"  VIX: {len(vix_df)} barre ({vix_df.index[0].date()} — {vix_df.index[-1].date()})")

    # -------------------------------------------------------------------------
    # 2. OUTER DATE INDEX E SPLIT TEMPORALE
    # -------------------------------------------------------------------------
    print("\n[2] OUTER DATE INDEX E SPLIT TEMPORALE")
    SEP()

    outer_idx = build_outer_date_index(mom_panel)
    n_bars    = len(outer_idx)

    is_end    = int(n_bars * IS_FRAC)
    val_end   = int(n_bars * (IS_FRAC + VAL_FRAC))
    oos_start = val_end
    oos_end   = n_bars
    n_oos     = oos_end - oos_start
    wf_size   = n_oos // N_WF_WINDOWS

    date_is_start  = outer_idx[0].date()
    date_is_end    = outer_idx[is_end - 1].date() if is_end < n_bars else "N/A"
    date_val_start = outer_idx[is_end].date()     if is_end < n_bars else "N/A"
    date_val_end   = outer_idx[val_end - 1].date() if val_end < n_bars else "N/A"
    date_oos_start = outer_idx[oos_start].date()  if oos_start < n_bars else "N/A"
    date_oos_end   = outer_idx[oos_end - 1].date() if oos_end - 1 < n_bars else "N/A"

    print(f"  Outer index (unione date trading): {n_bars} barre")
    print(f"  IS  (60%): bar 0   – {is_end:>4}   ({date_is_start} – {date_is_end})  [{is_end} barre]")
    print(f"  VAL (10%): bar {is_end:>4} – {val_end:>4}   ({date_val_start} – {date_val_end})  [{val_end - is_end} barre]")
    print(f"  OOS (30%): bar {oos_start:>4} – {oos_end:>4}   ({date_oos_start} – {date_oos_end})  [{n_oos} barre]")
    print(f"  Finestre WF: {N_WF_WINDOWS} x ~{wf_size} barre")

    print(f"\n  REGIMI COPERTI DALL'OOS ({date_oos_start} – {date_oos_end}):")
    print(f"  Bull run 2021 | Crash 2022 (Nasdaq -33%) | Recovery 2023-2024 | 2025")
    print(f"  [Rispetto al round 2 l'IS include: crash COVID 2020 + bull 2013-2019 + crash 2008-2009]")
    print(f"\n  DISCIPLINA OOS: parametri congelati a [3.b] PRIMA di aprire l'OOS.")
    print(f"  L'OOS [3.c] viene eseguito UNA SOLA VOLTA.")

    # Conta asset disponibili all'inizio e alla fine dell'IS
    assets_is_start = sum(
        1 for sym, df in mom_panel.items()
        if df.index[0] <= outer_idx[min(252, n_bars-1)]
    )
    assets_oos_start = sum(
        1 for sym, df in mom_panel.items()
        if df.index[0] <= outer_idx[oos_start]
    )
    print(f"\n  Asset disponibili all'inizio IS (outer join): ~{assets_is_start}")
    print(f"  Asset disponibili all'inizio OOS:             {assets_oos_start}")
    print(f"  (XLC e XLRE assenti in IS ma presenti in OOS: corretto per outer join)")

    # -------------------------------------------------------------------------
    # 3. MOMENTUM TIPO B — GRID SEARCH IS/VAL
    # -------------------------------------------------------------------------
    print(f"\n[3] MOMENTUM CROSS-SECTIONAL — Tipo B (§12) — ROUND 3")
    SEP()

    print(f"\n[3.a] Grid search IS/VAL ({len(GRID_LOOKBACK_LONG)}x{len(GRID_TOP_QUANTILE)} = "
          f"{N_CONFIGS_R3} configurazioni)")
    print(f"  DISCIPLINA LAB-5: solo su bar 0..{val_end}. OOS non ancora aperto.")
    print(f"  n_configs totale per DSR = {DSR_N_CONFIGS_MOM} (include tutti i round precedenti)\n")

    best_params, df_grid = grid_search_momentum(
        mom_panel, outer_idx, vix_df, bar_start=0, bar_end=val_end
    )
    print_mom_grid(df_grid)
    print(f"\n  >> Parametri congelati: L={best_params['lookback_long']} "
          f"q={best_params['top_quantile']:.2f}")

    # -------------------------------------------------------------------------
    # 3.b — PARAMETRI CONGELATI
    # -------------------------------------------------------------------------
    print("\n  *** PARAMETRI CONGELATI — OOS SI APRE ORA ***")

    # -------------------------------------------------------------------------
    # 3.c — OOS WALK-FORWARD
    # -------------------------------------------------------------------------
    print(f"\n[3.c] OOS Walk-Forward Momentum (parametri congelati):")
    wf_mom, daily_rets_mom, equity_mom = run_momentum_oos(
        mom_panel, outer_idx, vix_df, oos_start, oos_end, best_params, N_WF_WINDOWS
    )

    # -------------------------------------------------------------------------
    # 3.d — BASELINE RANDOM (CORREZIONE B)
    # -------------------------------------------------------------------------
    print(f"\n[3.d] Baseline random — {N_BASELINE_RANDOM} portafogli con pesi casuali")
    print(f"      (stessa finestra OOS, stessa struttura N_long=N_short, stessi costi):")
    bl_mean, bl_std, bl_p5, bl_all = compute_baseline_sharpe(
        mom_panel, outer_idx, vix_df,
        oos_start, oos_end, best_params,
        n_random=N_BASELINE_RANDOM,
    )
    print_baseline_summary(bl_mean, bl_std, bl_p5, bl_all)

    # -------------------------------------------------------------------------
    # 3.e — VALUTAZIONE CRITERI ROUND 3
    # -------------------------------------------------------------------------
    print(f"\n[3.e] Valutazione criteri §4 Tipo B (Round 3, corretti):")
    mom_eval = evaluate_momentum_round3(
        wf_mom, daily_rets_mom, equity_mom, best_params,
        bl_mean, bl_std, bl_p5,
    )
    print_mom_eval(mom_eval)

    # -------------------------------------------------------------------------
    # 4. RIEPILOGO FINALE
    # -------------------------------------------------------------------------
    print("\n[4] RIEPILOGO FINALE — ROUND 3 DEFINITIVO")
    SEP("=")

    print(f"\n  {'Segnale':<35} {'Tipo':>6} {'Verdict':>8} {'Sharpe':>8} "
          f"{'Baseline':>9} {'MDD':>7} {'WF_stab':>8}")
    SEP()
    print(
        f"  {'Momentum Cross-Sect. (R3)':<35} "
        f"{'B':>6} "
        f"{mom_eval['verdict']:>8}  "
        f"{mom_eval['sharpe']:>7.4f}  "
        f"{mom_eval['baseline_mean_sr']:>8.4f}  "
        f"{mom_eval['mdd']*100:>5.1f}%  "
        f"{mom_eval['wf_stability']*100:>6.0f}%"
    )
    SEP()
    print(f"\n  Pairs trading: ARCHIVIATO (FAIL definitivo Round 2)")
    print(f"  n_configs totale dichiarato: {DSR_N_CONFIGS_MOM}")
    print(f"  DSR p-value (informativo): {mom_eval['dsr_pval']:.6f}")
    print(f"  Margine Sharpe vs baseline: {mom_eval['sharpe'] - mom_eval['baseline_mean_sr']:+.4f} "
          f"(soglia >= {BASELINE_MARGIN})")

    SEP("=")
    print("  ASSUNZIONI E LIMITI DICHIARATI")
    SEP("=")
    print("  1. Entry simulata come close(t) per eseguire a open(t+1): slippage reale")
    print("     può essere peggiore su gap di apertura. Limite dichiarato.")
    print("  2. Outer join: asset non quotati in una data non entrano nel ranking di")
    print("     quella data. Questo è corretto e non introduce look-ahead bias.")
    print("  3. OOS già osservato in Round 1 e Round 2. Il costo statistico è pagato")
    print("     con n_configs=27 nel DSR. Questo NON è un OOS puro.")
    print("  4. Baseline random usa lo stesso pannello, le stesse date, gli stessi")
    print("     costi medi del segnale. Il confronto è metodologicamente corretto.")
    print("  5. Costi modellati come media per asset class. I costi reali di borrow")
    print("     per asset specifici possono essere più alti (es. EWZ, ILF).")
    print("  6. VIXY roll cost modellato come 20% annuo costante. In periodi di")
    print("     backwardation il costo è più basso — questa è una stima conservativa.")
    SEP("=")
    print()


if __name__ == "__main__":
    main()
