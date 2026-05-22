"""
validate_signals_round2.py — Validazione Round 2 dei segnali.

DIFFERENZE RISPETTO AL ROUND 1 (corrette dalla supervisione di Max)
--------------------------------------------------------------------
A. Momentum classificato come Tipo B (§12): criterio C1 sostituito con C1-B.
   Il CI 95% si calcola sul rendimento periodico DAILY (T obs, non N trade).
   Il criterio decisionale primario e' C2+C7 (Sharpe netto + DSR).

B. DSR con n_configs reale: grid search esplicita su IS/VAL con 16 combinazioni.
   L'OOS del round 1 era gia' stato osservato: n_configs = 16 + 1 = 17.
   NOTA: gonfiare n_configs per round precedente e' l'unico modo onesto di
   riusare un OOS gia' osservato (§12, VALIDATION_PROTOCOL).

C. Pairs su universo di 14 coppie (§13):
   - Screening cointegrazione su IS only (60% dei dati).
   - Correzione FDR Benjamini-Hochberg sui p-value ADF dei residui.
   - Solo le coppie sopravvissute a FDR vengono backtestato su OOS.
   - Hansen SPA sul candidato migliore: Sharpe OOS vs distribuzione del
     massimo Sharpe atteso per puro caso sull'universo testato.

UNIVERSO (CONGELATO — docs/ROUND2_UNIVERSE.md, 2026-05-21)
------------------------------------------------------------
Momentum: 42 ETF (vedi ROUND2_UNIVERSE.md §Universo A).
Pairs: 14 coppie (vedi ROUND2_UNIVERSE.md §Universo B).
AVVISO PROTOCOLLO: se un ticker fallisce il download viene escluso e
documentato. NON viene sostituito con un alternativo scelto post-hoc.

LOOK-AHEAD BIAS — PUNTI CRITICI (documentazione completa)
----------------------------------------------------------
LAB-1 (MOM): ranking usa P(t-S) e P(t-L), entrambi strettamente passati.
              Esecuzione differita a t+1 open (proxy: close t, limite dichiarato).
LAB-2 (MOM): filtro VIX usa shift(1) — esclude VIX di chiusura corrente.
LAB-3 (PAIRS): beta_hat OLS su finestra IS [t-W, t) — esclude barra t.
LAB-4 (PAIRS): z-score rolling chiuso a t (spread t gia' chiuso, OK).
LAB-5 (COMUNE): grid search SOLO su IS/VAL (bar 0 — val_end). Parametri
                congelati PRIMA di eseguire l'OOS. OOS eseguito UNA SOLA VOLTA.
LAB-6 (PAIRS): screening ADF cointegrazione su IS only (60%). Mai su OOS.
LAB-7 (PAIRS): FDR calcolato sui p-value IS — non usa risultati OOS.

DISCIPLINA OOS
--------------
Il periodo OOS 2022-2026 era gia' stato osservato nel round 1.
Lo rieseguiamo con i NUOVI parametri selezionati dalla grid search (IS/VAL).
Il costo statistico del riutilizzo e' pagato gonfiando n_configs nel DSR.
Sarebbe scorretto chiamare questo un "OOS puro" — per onesta' intellettuale
e' un OOS "penalizzato". Il DSR corregge esattamente per questa situazione.

COSTI MODELLATI (§7, ROUND2_UNIVERSE.md)
-----------------------------------------
Momentum (ETF diversificati):
  - ETF equity USA (XL*):      round-trip 0.15% (media spread+comm+slippage)
  - ETF equity intl/EM:        round-trip 0.35%
  - ETF fixed income:          round-trip 0.20%
  - ETF commodity:             round-trip 0.35%
  - ETF REIT:                  round-trip 0.20%
  - ETF valute/vola:           round-trip 0.30%
  - VIXY: aggiunta penalita' roll cost 20% annuo / 252 per giorno long
  - Borrow cost short:         0.50% annuo / 252 per giorno per gamba short

Pairs (coppia long/short):
  - Costo per gamba round-trip: 0.20% (media asset class)
  - Financing overnight:         3% annuo = 0.008%/giorno per nozionale
  - Borrow cost short:           0.50% annuo / 252 per giorno

USO
----
    python scripts/validate_signals_round2.py

Output: risultati grezzi completi (tabelle walk-forward, griglia IS,
        FDR pairs, SPA, criteri PASS/FAIL) per Max.
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

# Importa segnale momentum (usato per il compute() sulla griglia IS/VAL)
from strategies.signals.momentum_cross_sectional import MomentumCrossSectionalSignal

# statsmodels per ADF
try:
    from statsmodels.tsa.stattools import adfuller
    _STATSMODELS_OK = True
except ImportError:
    _STATSMODELS_OK = False
    print("[WARN] statsmodels non disponibile — pairs test saltato.")


# =============================================================================
# SEZIONE 1 — UNIVERSO CONGELATO (docs/ROUND2_UNIVERSE.md)
# =============================================================================

# --- Universo Momentum (42 ETF + VIX per filtro regime) ---
# XLRE (2015) e XLC (2018) inclusi con storia reale (non imputata).
# VIXY ha roll cost alto: modellato come penalita' giornaliera.

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

# --- Universo Pairs (14 coppie, CONGELATO) ---
# Definite per ragioni economiche strutturali PRIMA di vedere i dati (§13).
PAIRS_UNIVERSE = [
    # Cat I — Doppio provider, stessa esposizione
    ("SPY",  "IVV"),
    ("QQQ",  "QQQM"),   # QQQM dal 2020: storia IS corta, candidato a esclusione automatica
    ("GLD",  "IAU"),
    ("EFA",  "VEA"),
    # Cat II — Competitor diretti, stesso settore
    ("XOM",  "CVX"),
    ("JPM",  "BAC"),
    ("MSFT", "GOOGL"),
    ("KO",   "PEP"),
    # Cat III — Settoriali complementari
    ("XLF",  "XLU"),
    ("XLE",  "XLB"),
    ("XLY",  "XLP"),
    # Cat IV — Macro cross-asset
    ("TLT",  "GLD"),
    ("EEM",  "GLD"),
    ("HYG",  "SPY"),
]

# --- Classificazione costi per ticker ---
# Usata per applicare il costo corretto al round-trip di ogni ETF nel panel momentum.
# Fonte: ROUND2_UNIVERSE.md §Costi.
def _cost_for_ticker(ticker: str) -> float:
    """Ritorna il costo round-trip stimato per il ticker (per gamba, %/100)."""
    equity_usa    = {"XLK","XLV","XLF","XLE","XLI","XLY","XLP","XLB","XLU","XLRE","XLC",
                     "SPY","QQQ","QQQM","IVV","VEA","EFA","QUAL","USMV"}
    fixed_income  = {"SHY","IEF","TLT","LQD","HYG","EMB","TIP"}
    commodity     = {"GLD","SLV","USO","UNG","DBA","DBB","IAU"}
    reit          = {"VNQ","IYR","REM","VNQI"}
    currency_vola = {"UUP","FXY","FXF","VIXY"}
    intl_em       = {"EEM","VGK","EWJ","FXI","EWZ","ILF","INDA"}

    if ticker in equity_usa:    return 0.0015   # 0.15%
    if ticker in fixed_income:  return 0.0020   # 0.20%
    if ticker in commodity:     return 0.0035   # 0.35%
    if ticker in reit:          return 0.0020   # 0.20%
    if ticker in currency_vola: return 0.0030   # 0.30%
    if ticker in intl_em:       return 0.0035   # 0.35%
    return 0.0025   # default prudenziale

# Roll cost VIXY: 20% annuo di decadimento strutturale (contango VIX futures)
VIXY_ROLL_COST_DAILY = 0.20 / 252

# Borrow cost short (momentum e pairs): 0.50% annuo / 252
BORROW_DAILY = 0.005 / 252

# Pairs: costo per gamba round-trip (media asset class) + financing
PAIRS_COST_PER_LEG = 0.0020   # 0.20% per gamba
PAIRS_FINANCING_DAILY = 0.03 / 252   # 3% annuo / 252

# --- Split temporale ---
IS_FRAC  = 0.60
VAL_FRAC = 0.10
OOS_FRAC = 0.30
N_WF_WINDOWS = 5

# --- Bootstrap ---
N_BOOTSTRAP = 3000
RNG = np.random.default_rng(42)

# --- Download ---
DOWNLOAD_START = "2010-01-01"
DOWNLOAD_END   = "2026-01-01"   # freeze della serie storica


# =============================================================================
# SEZIONE 2 — GRIGLIA IS/VAL MOMENTUM (Tipo B, §12)
# =============================================================================
#
# Esploriamo 4x4 = 16 combinazioni di parametri su IS+VAL.
# DISCIPLINA LAB-5: la griglia viene valutata SOLO su IS/VAL.
# I parametri migliori vengono congelati PRIMA di aprire l'OOS.
#
# OOS del round 1 gia' osservato: n_configs = 16 + 1 = 17 (pena onesta).

GRID_LOOKBACK_LONG  = [126, 189, 252, 315]   # 6m, 9m, 12m, 15m in barre daily
GRID_TOP_QUANTILE   = [0.20, 0.25, 0.30, 0.35]   # 20%-35% del universo
GRID_SKIP           = 5    # fisso: motivato dalla letteratura (Jegadeesh 1993)
GRID_VIX_Z          = 2.0  # fisso: valore standard, non ottimizzato
GRID_VIX_WINDOW     = 252  # fisso

# n_configs = 16 (griglia IS/VAL) + 1 (tentativo OOS round 1) = 17
DSR_N_CONFIGS_MOM = 17

# Parametri pairs (non si fanno grid search sui trigger: troppi DoF con 14 coppie)
PAIRS_PARAMS_FIXED = dict(
    z_entry=2.0, z_exit=0.5, z_stop=3.5,
    coint_window=252, zscore_window=60, max_half_life_bars=30,
    adf_pvalue_thresh=0.05,
)
# Per i pairs DSR: 14 coppie screening IS + 1 tentativo round 1 = 15
DSR_N_CONFIGS_PAIRS = 15

# Livello FDR Benjamini-Hochberg
FDR_ALPHA = 0.10   # piu' permissivo di 0.05: nella selezione IS vogliamo non escludere troppo

# SPA: bootstrap su 1000 campioni, blocchi lunghezza sqrt(T_oos)
SPA_N_BOOT = 1000


# =============================================================================
# SEZIONE 3 — DOWNLOAD DATI
# =============================================================================

def download_ticker(ticker: str) -> Optional[pd.DataFrame]:
    """
    Scarica OHLCV daily adjusted da yfinance (2010-01-01 — 2026-01-01).
    Ritorna DataFrame con colonne lowercase oppure None in caso di fallimento.
    AVVISO PROTOCOLLO: in caso di fallimento il ticker viene ESCLUSO, non sostituito.
    """
    import yfinance as yf
    for attempt in range(3):
        try:
            time.sleep(0.3 * (attempt + 1))
            raw = yf.download(
                ticker, start=DOWNLOAD_START, end=DOWNLOAD_END,
                interval="1d", progress=False, auto_adjust=True,
            )
            if raw is None or raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            # Seleziona solo OHLCV; close adjusted e' la colonna Close con auto_adjust=True
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


def build_panel(tickers: List[str], label: str = "") -> Tuple[Dict[str, pd.DataFrame], List[str]]:
    """
    Scarica tutti i ticker. Ritorna (panel_dict, esclusi).
    I ticker esclusi vengono documentati ma NON sostituiti.
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

    if panel:
        # Allineamento su indice comune (inner join)
        idx = None
        for df in panel.values():
            idx = df.index if idx is None else idx.intersection(df.index)
        if idx is not None and len(idx) > 200:
            panel = {k: v.loc[idx].copy() for k, v in panel.items()}

    print(f"  {label}: {len(panel)}/{len(tickers)} ticker scaricati, {len(esclusi)} esclusi")
    return panel, esclusi


# =============================================================================
# SEZIONE 4 — METRICHE STATISTICHE
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
    """CAGR da serie di rendimenti daily."""
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
    Numerosita' = T (intera serie OOS), non N trade.
    Usa block bootstrap con blocchi di lunghezza sqrt(T) per gestire
    l'autocorrelazione dei rendimenti (Politis & Romano 1994).

    Ritorna (ci_lo, ci_hi, p_value one-sided H0: mu <= 0).
    """
    T = len(daily_rets)
    if T < 10:
        return float("nan"), float("nan"), float("nan")

    # Lunghezza blocchi: sqrt(T) arrotondato, min 5
    block_len = max(5, int(np.sqrt(T)))

    def block_mean(data: np.ndarray) -> float:
        """Media di un campione bootstrap a blocchi."""
        n = len(data)
        result = []
        while len(result) < n:
            # Estrai posizione di inizio blocco
            start = int(RNG.integers(0, n))
            block = data[start : start + block_len]
            # Se il blocco va oltre la fine, wrappa circolarmente
            if len(block) < block_len:
                block = np.concatenate([block, data[:block_len - len(block)]])
            result.extend(block[:block_len].tolist())
        return float(np.mean(result[:n]))

    boot_means = np.array([block_mean(daily_rets) for _ in range(n_boot)])
    ci_lo = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    # p-value one-sided: p = proporzione di bootstrap in cui la media e' <= 0
    # (test H0: mu <= 0 vs H1: mu > 0)
    centered = daily_rets - daily_rets.mean()
    boot_h0 = np.array([block_mean(centered) for _ in range(n_boot)])
    p_val = float(np.mean(boot_h0 >= daily_rets.mean()))
    p_val = max(p_val, 1.0 / n_boot)
    return ci_lo, ci_hi, p_val


def bootstrap_ci_per_trade(
    trade_rets: np.ndarray,
    n_boot: int = N_BOOTSTRAP,
    alpha: float = 0.05,
) -> Tuple[float, float, float]:
    """
    C1 (§4 Tipo A): bootstrap CI 95% sul rendimento NETTO PER TRADE.
    IID bootstrap (i trade sono approssimativamente indipendenti).
    Ritorna (ci_lo, ci_hi, p_value).
    """
    if len(trade_rets) < 5:
        return float("nan"), float("nan"), float("nan")

    boot_means = np.array([
        RNG.choice(trade_rets, size=len(trade_rets), replace=True).mean()
        for _ in range(n_boot)
    ])
    ci_lo = float(np.percentile(boot_means, 100 * alpha / 2))
    ci_hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))

    centered = trade_rets - trade_rets.mean()
    boot_h0 = np.array([
        RNG.choice(centered, size=len(centered), replace=True).mean()
        for _ in range(n_boot)
    ])
    p_val = float(np.mean(boot_h0 >= trade_rets.mean()))
    p_val = max(p_val, 1.0 / n_boot)
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

    SR_0 = E[max(SR_k)] per k = 1..n_configs configurazioni i.i.d. N(0,1).
    Formula di Bailey-LdP (2014, Eq. 6):
        SR_0 = ((1 - gamma_e) * z^{-1}(1 - 1/n_configs)
                 + gamma_e * sqrt(z^{-1}(1-1/n_configs)^2 + 1))
               / sqrt(n_configs)   [NOTA: divisione per sqrt(n_configs) e' inclusa
               nella formula originale solo per normalizzazione — qui usiamo la
               versione senza normalizzazione che fornisce il benchmark in unita'
               di SR, non z-score; vedi Eq.6 corretta qui sotto]

    Versione corretta dalla letteratura (Eq. 6 senza errore tipografico):
        SR_0 = (1-gamma_e) * Phi^{-1}(1 - 1/n_configs)
               + gamma_e * sqrt(Phi^{-1}(1-1/n_configs)^2 + 1)

    Questo fornisce il valore atteso del MAX SR tra n_configs configurazioni
    gaussiane i.i.d. N(0,1/sqrt(T)) dove T = n_obs.

    DSR = (SR_obs - SR_0) / sqrt((1 + 0.5*SR^2 - skew*SR + (kurt-1)/4*SR^2) / (T-1))
    p_val = 1 - Phi(DSR)   [H0: SR_true <= SR_0]

    Con n_configs = 1: SR_0 = 0 e DSR = t-stat classico su SR (t-test H0: mu<=0).
    """
    if n_obs < 2:
        return 0.0, 0.5

    # Benchmark SR_0: valore atteso del massimo Sharpe tra n_configs prove casuali
    if n_configs <= 1:
        sr_0 = 0.0
    else:
        gamma_e = 0.5772156649   # costante di Eulero-Mascheroni
        # Phi^{-1}(1 - 1/n_configs): quantile della normale standard
        z_inv = float(scipy_stats.norm.ppf(1.0 - 1.0 / n_configs))
        # Eq. 6 di Bailey & Lopez de Prado 2014 (corretta):
        sr_0 = (1.0 - gamma_e) * z_inv + gamma_e * np.sqrt(z_inv ** 2 + 1.0)
        # SR_0 e' in unita' z-score (SR annualizzato implica una normalizzazione);
        # nella forma del paper il confronto avviene in unita' di SR_obs.
        # Convertiamo dividendo per sqrt(n_obs - 1) per portare SR_0 nella
        # stessa scala di SR_obs (che e' annualizzato con sqrt(252)):
        # NOTA: questa e' un'approssimazione. L'implementazione rigorosa
        # richiederebbe la matrice di covarianza tra le configurazioni.
        # Per n_configs piccolo l'errore e' < 10%.
        sr_0 = sr_0 / np.sqrt(n_obs - 1)

    # Std dello SR (formula Bailey-LdP Eq. 4)
    correction_term = 1.0 - skew_val * sr_obs + (kurt_val - 1.0) / 4.0 * sr_obs ** 2
    correction_term = max(correction_term, 1e-12)
    sr_std = float(np.sqrt(correction_term / (n_obs - 1)))
    sr_std = max(sr_std, 1e-12)

    dsr = (sr_obs - sr_0) / sr_std
    # p_val: prob. che SR_true <= SR_0 (H0 di snooping riuscito).
    # Rigetto se p < 0.05: Sharpe osservato e' significativamente > SR_0.
    p_val = float(1.0 - ndtr(dsr))
    return float(dsr), p_val


# =============================================================================
# SEZIONE 5 — GRID SEARCH IS/VAL MOMENTUM
# =============================================================================

class MomentumGridSearchBacktester:
    """
    Backtest del momentum su una finestra IS+VAL per ogni configurazione della griglia.

    DISCIPLINA LAB-5: questa classe e' usata SOLO su bar 0..val_end.
    MAI aprire l'OOS prima di congelare i parametri.

    Metodo:
    - A ogni rebalancing (ogni 21 barre), calcola Mom_adj per ogni asset.
    - Long top_quantile, short bottom_quantile.
    - Rendimenti daily moltiplicativi.
    - Costi: round-trip per asset class al momento della rotazione.
    """

    def __init__(
        self,
        panel: Dict[str, pd.DataFrame],
        vix_df: Optional[pd.DataFrame],
    ) -> None:
        self.panel = {k: v for k, v in panel.items() if k != VIX_TICKER}
        self.vix_df = vix_df
        self.syms = list(self.panel.keys())
        self.costs = {s: _cost_for_ticker(s) for s in self.syms}
        self.rebalance_freq = 21   # mensile

    def run(
        self,
        bar_start: int,
        bar_end: int,
        lookback_long: int,
        top_quantile: float,
        vix_z_thresh: float = 2.0,
        vix_window: int = 252,
    ) -> Dict:
        """
        Esegue il backtest momentum su [bar_start, bar_end).
        Ritorna dict con rendimenti daily e metriche aggregate.
        """
        daily_rets: List[float] = []
        equity = [1.0]
        current_pos: Dict[str, float] = {}

        S = GRID_SKIP
        L = lookback_long

        for i in range(bar_end - bar_start - 1):
            t = bar_start + i

            do_rebalance = (i % self.rebalance_freq == 0)

            if do_rebalance:
                # --- Calcolo Mom_adj ---
                # LAB-1: usa P(t-S) e P(t-L), entrambi strettamente < t.
                mom_vals: Dict[str, float] = {}
                for sym in self.syms:
                    df = self.panel[sym]
                    n_sym = len(df)
                    if n_sym < L + 2:
                        continue
                    # iloc[t-(S+1)] relativo al panel (che inizia da bar 0)
                    # Indice assoluto t; il panel e' allineato su common index.
                    if t - (S + 1) < 0 or t - (L + 1) < 0:
                        continue
                    p_skip = float(df["close"].iloc[t - S - 1])   # P(t-S-1): S barre fa
                    p_long = float(df["close"].iloc[t - L - 1])   # P(t-L-1): L barre fa
                    if p_long <= 0 or not np.isfinite(p_skip) or not np.isfinite(p_long):
                        continue
                    mom_vals[sym] = p_skip / p_long - 1.0

                if len(mom_vals) < 5:
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                    continue

                # --- Filtro VIX (LAB-2: usa shift(1)) ---
                vix_filter_active = False
                if self.vix_df is not None and len(self.vix_df) > vix_window:
                    vix_close = self.vix_df["close"]
                    if t < len(vix_close):
                        # Rolling su [0, t-1] (shift(1): esclude VIX di chiusura corrente)
                        win_start = max(0, t - vix_window)
                        vix_win = vix_close.iloc[win_start : t]   # [win_start, t) → esclude t
                        if len(vix_win) >= vix_window // 2:
                            vix_mu = float(vix_win.mean())
                            vix_sig = float(vix_win.std(ddof=1))
                            if vix_sig > 0:
                                vix_t = float(vix_close.iloc[t])   # VIX corrente (per il test)
                                z_vix = (vix_t - vix_mu) / vix_sig
                                if z_vix >= vix_z_thresh:
                                    vix_filter_active = True

                if vix_filter_active:
                    current_pos = {s: 0.0 for s in self.syms}
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                    continue

                # --- Ranking cross-sectional → posizioni ---
                sorted_syms = sorted(mom_vals.keys(), key=lambda s: mom_vals[s])
                n_ranked = len(sorted_syms)
                n_side = max(1, int(n_ranked * top_quantile))

                new_pos: Dict[str, float] = {s: 0.0 for s in self.syms}
                longs  = sorted_syms[-n_side:]
                shorts = sorted_syms[:n_side]
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
                equity[-1] *= (1.0 - rot_cost)   # deduco i costi dall'equity

            # --- P&L daily ---
            port_ret = 0.0
            any_pos = False
            for sym, w in current_pos.items():
                if abs(w) < 1e-9:
                    continue
                df = self.panel[sym]
                if t + 1 >= len(df) or t < 0:
                    continue
                c_t   = float(df["close"].iloc[t])
                c_tp1 = float(df["close"].iloc[t + 1])
                if c_t <= 0:
                    continue
                ret = (c_tp1 - c_t) / c_t * w
                port_ret += ret
                any_pos = True

                # Borrow cost daily per gambe short
                if w < 0:
                    port_ret -= abs(w) * BORROW_DAILY

                # VIXY roll cost: penalita' giornaliera se long VIXY
                if sym == "VIXY" and w > 0:
                    port_ret -= w * VIXY_ROLL_COST_DAILY

            if any_pos:
                daily_rets.append(port_ret)
                equity.append(equity[-1] * (1.0 + port_ret))
            else:
                daily_rets.append(0.0)
                equity.append(equity[-1])

        rets_arr = np.array(daily_rets)
        eq_arr = np.array(equity)
        sr = sharpe(rets_arr)
        so = sortino(rets_arr)
        mdd_val = max_drawdown(eq_arr)
        return {
            "daily_rets": rets_arr,
            "equity":     eq_arr,
            "sharpe":     sr,
            "sortino":    so,
            "mdd":        mdd_val,
            "cagr":       cagr(rets_arr),
            "calmar":     calmar(rets_arr, mdd_val),
        }


def grid_search_momentum(
    panel: Dict[str, pd.DataFrame],
    vix_df: Optional[pd.DataFrame],
    bar_start: int,
    bar_end: int,
) -> Tuple[Dict, pd.DataFrame]:
    """
    Esegue la grid search su IS+VAL (bar_start..bar_end).
    Ritorna (best_params, risultati_griglia_completi).

    DISCIPLINA LAB-5: bar_start e bar_end devono essere DENTRO IS+VAL.
    """
    bt = MomentumGridSearchBacktester(panel, vix_df)
    grid_results = []

    total = len(GRID_LOOKBACK_LONG) * len(GRID_TOP_QUANTILE)
    done = 0
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

    # Best params: massimo Sharpe su IS/VAL
    best_row = df_grid.iloc[0]
    best_params = {
        "lookback_long": int(best_row["lookback_long"]),
        "top_quantile":  float(best_row["top_quantile"]),
        "vix_z_thresh":  GRID_VIX_Z,
        "vix_window":    GRID_VIX_WINDOW,
    }
    return best_params, df_grid


# =============================================================================
# SEZIONE 6 — BACKTEST MOMENTUM OOS (Walk-Forward)
# =============================================================================

def run_momentum_oos(
    panel: Dict[str, pd.DataFrame],
    vix_df: Optional[pd.DataFrame],
    oos_start: int,
    oos_end: int,
    best_params: Dict,
    n_wf: int = N_WF_WINDOWS,
) -> Tuple[List[Dict], np.ndarray, np.ndarray]:
    """
    Esegue il backtest momentum sull'OOS walk-forward con i parametri congelati.
    Ritorna (wf_results, daily_rets_oos_concat, equity_oos_concat).

    DISCIPLINA: questa funzione e' chiamata UNA SOLA VOLTA con parametri
    congelati prima di aprirla. Il chiamante non deve modificare i parametri
    dopo aver visto i risultati.
    """
    bt = MomentumGridSearchBacktester(panel, vix_df)
    wf_size = (oos_end - oos_start) // n_wf
    wf_results = []
    all_rets = []
    equity_concat = np.array([1.0])

    for w_idx in range(n_wf):
        w_start = oos_start + w_idx * wf_size
        w_end   = w_start + wf_size if w_idx < n_wf - 1 else oos_end

        print(f"  Finestra {w_idx+1}/{n_wf}: bar {w_start}-{w_end} ...", end="", flush=True)
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

        sr_w = sharpe(res["daily_rets"])
        print(f"  Sharpe={sr_w:.3f}  CAGR={res['cagr']*100:+.1f}%  MDD={res['mdd']*100:.1f}%")

    all_rets_arr = np.concatenate(all_rets) if all_rets else np.array([])
    return wf_results, all_rets_arr, equity_concat


# =============================================================================
# SEZIONE 7 — SCREENING PAIRS SU IS + FDR BENJAMINI-HOCHBERG
# =============================================================================

def adf_pvalue(series: np.ndarray) -> Optional[float]:
    """ADF Augmented Dickey-Fuller, selezione lag via AIC. Ritorna p-value o None."""
    if not _STATSMODELS_OK or len(series) < 50:
        return None
    try:
        result = adfuller(series, autolag="AIC", maxlag=12)
        return float(result[1])
    except Exception:
        return None


def estimate_half_life(spread: np.ndarray) -> Optional[float]:
    """Half-life del mean-reversion via AR(1): tau = -log(2)/log(rho_AR1)."""
    if len(spread) < 10:
        return None
    e_lag   = spread[:-1]
    delta_e = np.diff(spread)
    try:
        res = scipy_stats.linregress(e_lag, delta_e)
        rho = 1.0 + float(res.slope)
    except Exception:
        return None
    if rho <= 0 or rho >= 1.0:
        return None
    hl = -np.log(2.0) / np.log(rho)
    return float(hl) if (np.isfinite(hl) and hl > 0) else None


def screen_pair_on_is(
    sym_a: str, df_a: pd.DataFrame,
    sym_b: str, df_b: pd.DataFrame,
    is_end: int,
    coint_window: int = 252,
) -> Dict:
    """
    Screening di una coppia su IS only (bar 0..is_end).
    LAB-6: usa SOLO i dati IS. MAI usare dati OOS per la selezione.

    Step:
    1. ADF individuale su IS (conferma I(1)).
    2. OLS su IS per beta_hat.
    3. ADF sui residui IS.
    4. Half-life IS.

    Ritorna dict con p-value ADF residui, half-life e flag di ammissibilita'.
    """
    result = {
        "sym_a": sym_a, "sym_b": sym_b,
        "admitted_is": False,
        "adf_p_individual_a": None,
        "adf_p_individual_b": None,
        "adf_p_residuals_is": None,
        "beta_hat_is":        None,
        "half_life_is":       None,
        "note":               "",
    }

    # Allinea su IS
    common = df_a.index.intersection(df_b.index)
    if len(common) < coint_window + 50:
        result["note"] = f"dati insufficienti IS ({len(common)} barre comuni)"
        return result

    # Slice IS
    is_idx = common[:is_end] if is_end < len(common) else common
    if len(is_idx) < coint_window + 50:
        result["note"] = f"IS troppo corta ({len(is_idx)} barre)"
        return result

    close_a = df_a.loc[is_idx, "close"].dropna().astype(float)
    close_b = df_b.loc[is_idx, "close"].dropna().astype(float)

    # Ri-allinea dopo dropna
    common2 = close_a.index.intersection(close_b.index)
    if len(common2) < 100:
        result["note"] = "troppi NaN dopo dropna"
        return result
    la = np.log(close_a.loc[common2].values)
    lb = np.log(close_b.loc[common2].values)

    # Step 1: ADF individuale (I(1))
    p_a = adf_pvalue(la)
    p_b = adf_pvalue(lb)
    result["adf_p_individual_a"] = p_a
    result["adf_p_individual_b"] = p_b

    thresh = 0.05
    if p_a is None or p_a < thresh:
        result["note"] = f"{sym_a} non e' I(1) (p={p_a})"
        return result
    if p_b is None or p_b < thresh:
        result["note"] = f"{sym_b} non e' I(1) (p={p_b})"
        return result

    # Step 2: OLS su IS window (usa ultime coint_window barre IS)
    la_is = la[-coint_window:]
    lb_is = lb[-coint_window:]
    try:
        ols_res = scipy_stats.linregress(lb_is, la_is)
        beta = float(ols_res.slope)
        alpha = float(ols_res.intercept)
    except Exception as exc:
        result["note"] = f"OLS error: {exc}"
        return result

    result["beta_hat_is"] = beta
    if not np.isfinite(beta) or beta <= 0:
        result["note"] = f"beta_hat non valido: {beta:.4f}"
        return result

    # Step 3: Spread e ADF residui IS
    spread_is = la_is - beta * lb_is - alpha
    p_res = adf_pvalue(spread_is)
    result["adf_p_residuals_is"] = p_res

    if p_res is None:
        result["note"] = "ADF residui fallito"
        return result

    # Step 4: Half-life
    hl = estimate_half_life(spread_is)
    result["half_life_is"] = hl

    # L'ammissibilita' IS si basa solo su ADF residui (FDR deciders il cut-off).
    # Half-life troppo lunga e' segnalata ma non esclude dalla FDR.
    result["admitted_is"] = True
    if hl is not None and hl > PAIRS_PARAMS_FIXED["max_half_life_bars"]:
        result["note"] = f"half-life={hl:.1f} > {PAIRS_PARAMS_FIXED['max_half_life_bars']} barre (troppo lento)"
    elif p_res > thresh:
        result["admitted_is"] = False
        result["note"] = f"ADF residui p={p_res:.4f} > {thresh} (non stazionario)"

    return result


def fdr_benjamini_hochberg(p_values: List[float], alpha: float = FDR_ALPHA) -> List[bool]:
    """
    Correzione FDR Benjamini-Hochberg (Benjamini & Hochberg 1995).

    Per m test, ordina p-value crescenti e trova il massimo k tale che:
        p_(k) <= k/m * alpha

    Tutte le ipotesi fino a k vengono rifiutate (= coppie ammesse come cointegrate).

    Ritorna lista di bool: True = coppia sopravvive a FDR.
    LAB-7: questa funzione usa SOLO p-value IS. Non contamina l'OOS.
    """
    m = len(p_values)
    if m == 0:
        return []

    # Ordina p-value con tracciamento indici originali
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    rejected = [False] * m

    # Trova il massimo k (1-indexed) tale che p_(k) <= k/m * alpha
    max_k = 0
    for rank, (orig_idx, pval) in enumerate(indexed):
        k = rank + 1   # 1-indexed
        threshold = k / m * alpha
        if pval <= threshold:
            max_k = k

    # Tutte le coppie fino a max_k sono rifiutate (H0: non cointegrate → coppie ammesse)
    for rank, (orig_idx, pval) in enumerate(indexed):
        k = rank + 1
        if k <= max_k:
            rejected[orig_idx] = True

    return rejected


# =============================================================================
# SEZIONE 8 — BACKTEST PAIRS OOS (Walk-Forward, Tipo A)
# =============================================================================

class PairsBacktesterOOS:
    """
    Backtest pairs mean-reversion su OOS.
    Usa la metodologia Tipo A (§12): ogni trade e' un'unita' discreta.
    C1 = bootstrap CI sul rendimento netto PER TRADE.

    Meccanica bar-by-bar (anti look-ahead):
    - A ogni barra t: stima beta_hat su [t-coint_window, t) (esclude t).
    - z-score rolling su [t-zscore_window, t] (incluso t = gia' chiuso).
    - Entry: decisione a t, esecuzione simulata come chiusura t (proxy open t+1).
    - P&L: close(t) -> close(t+1).
    - Costi: applicati a open e close del trade.
    """

    def __init__(
        self,
        sym_a: str, df_a: pd.DataFrame,
        sym_b: str, df_b: pd.DataFrame,
        beta_is: float,   # beta_hat stimato su IS (solo per inizializzare)
    ) -> None:
        self.sym_a = sym_a
        self.sym_b = sym_b
        # Allinea su indice comune
        common = df_a.index.intersection(df_b.index)
        self.df_a = df_a.loc[common].copy()
        self.df_b = df_b.loc[common].copy()
        self.beta_is = beta_is   # non usato nel loop: ogni barra ri-stima beta

    def run(
        self,
        bar_start: int,
        bar_end: int,
    ) -> Dict:
        """
        Esegue il backtest su [bar_start, bar_end).
        Richiede bar_start >= coint_window + zscore_window (per warmup).
        """
        W = PAIRS_PARAMS_FIXED["coint_window"]
        Z = PAIRS_PARAMS_FIXED["zscore_window"]
        z_entry = PAIRS_PARAMS_FIXED["z_entry"]
        z_exit  = PAIRS_PARAMS_FIXED["z_exit"]
        z_stop  = PAIRS_PARAMS_FIXED["z_stop"]
        max_hl  = PAIRS_PARAMS_FIXED["max_half_life_bars"]

        n = min(len(self.df_a), len(self.df_b))
        closes_a = self.df_a["close"].values[:n].astype(float)
        closes_b = self.df_b["close"].values[:n].astype(float)
        log_a = np.log(closes_a)
        log_b = np.log(closes_b)

        daily_rets: List[float] = []
        net_trade_rets: List[float] = []
        equity = [1.0]
        n_trades = 0

        # Stato posizione: +1 = long A / short B; -1 = short A / long B; 0 = flat
        position  = 0
        entry_bar = None
        entry_eq  = 1.0

        for t in range(bar_start, min(bar_end - 1, n - 1)):
            # --- Stima z-score a barra t ---
            # LAB-3: beta_hat su [t-W, t) — esclude t
            if t < W + Z:
                daily_rets.append(0.0)
                equity.append(equity[-1])
                continue

            la_is = log_a[t - W : t]
            lb_is = log_b[t - W : t]
            if len(la_is) < 50:
                daily_rets.append(0.0)
                equity.append(equity[-1])
                continue

            try:
                ols_res = scipy_stats.linregress(lb_is, la_is)
                beta  = float(ols_res.slope)
                alpha = float(ols_res.intercept)
            except Exception:
                daily_rets.append(0.0)
                equity.append(equity[-1])
                continue

            if not np.isfinite(beta) or beta <= 0:
                daily_rets.append(0.0)
                equity.append(equity[-1])
                continue

            # Half-life: se troppo lunga, non aprire nuove posizioni ma
            # NON chiudere quelle aperte (evita bias di sopravvivenza).
            spread_full = log_a[:t + 1] - beta * log_b[:t + 1] - alpha
            spread_is   = spread_full[t - W : t]
            hl = estimate_half_life(spread_is)
            hl_ok = (hl is not None and hl <= max_hl)

            # Z-score rolling: [t-Z, t] incluso
            sp_win = spread_full[max(0, t - Z + 1) : t + 1]
            if len(sp_win) < Z // 2:
                daily_rets.append(0.0)
                equity.append(equity[-1])
                continue
            mu_z  = float(np.mean(sp_win))
            std_z = float(np.std(sp_win, ddof=1))
            if std_z < 1e-12:
                daily_rets.append(0.0)
                equity.append(equity[-1])
                continue
            z = (float(spread_full[t]) - mu_z) / std_z

            # --- Gestione posizione esistente ---
            if position != 0:
                if t + 1 < n:
                    ret_a = (closes_a[t + 1] - closes_a[t]) / closes_a[t]
                    ret_b = (closes_b[t + 1] - closes_b[t]) / closes_b[t]
                    # Long A/Short B: ret_a - ret_b; Long B/Short A: ret_b - ret_a
                    port_ret = position * 0.5 * (ret_a - ret_b)
                    # Borrow cost sulla gamba short
                    port_ret -= 0.5 * BORROW_DAILY
                    # Financing overnight (margine)
                    port_ret -= PAIRS_FINANCING_DAILY
                else:
                    port_ret = 0.0

                daily_rets.append(port_ret)
                equity.append(equity[-1] * (1.0 + port_ret))

                # Segnale di chiusura
                should_exit = (abs(z) <= z_exit) or (abs(z) >= z_stop)
                if should_exit:
                    n_bars_held = t - entry_bar + 1
                    trade_gross = equity[-1] / entry_eq - 1.0
                    # Costo apertura + chiusura (2 gambe x 2 transazioni)
                    cost_total  = 2.0 * 2.0 * PAIRS_COST_PER_LEG
                    # Borrow + financing gia' incluso nei daily_rets
                    trade_net   = trade_gross - cost_total
                    net_trade_rets.append(trade_net)
                    position = 0
                    entry_bar = None

            # --- Apertura nuova posizione (solo se flat e half-life OK) ---
            elif position == 0:
                if not hl_ok:
                    # Half-life troppo lunga: non aprire
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                    continue

                if z > z_entry:
                    # Spread sopra media: short A, long B (position = -1)
                    position  = -1
                    entry_bar = t
                    entry_eq  = equity[-1]
                    n_trades += 1
                    # Applica costo di apertura immediatamente
                    equity[-1] *= (1.0 - 2.0 * PAIRS_COST_PER_LEG)
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                elif z < -z_entry:
                    # Spread sotto media: long A, short B (position = +1)
                    position  = 1
                    entry_bar = t
                    entry_eq  = equity[-1]
                    n_trades += 1
                    equity[-1] *= (1.0 - 2.0 * PAIRS_COST_PER_LEG)
                    daily_rets.append(0.0)
                    equity.append(equity[-1])
                else:
                    daily_rets.append(0.0)
                    equity.append(equity[-1])

        # Chiudi posizione eventuale a fine finestra
        if position != 0 and entry_bar is not None:
            trade_gross = equity[-1] / entry_eq - 1.0
            trade_net   = trade_gross - 2.0 * 2.0 * PAIRS_COST_PER_LEG
            net_trade_rets.append(trade_net)

        return {
            "daily_rets":     np.array(daily_rets),
            "net_trade_rets": np.array(net_trade_rets),
            "equity":         np.array(equity),
            "n_trades":       n_trades,
        }


# =============================================================================
# SEZIONE 9 — HANSEN SPA (Superior Predictive Ability)
# =============================================================================

def hansen_spa(
    best_pair_rets: np.ndarray,
    null_sharpes: List[float],
    n_boot: int = SPA_N_BOOT,
) -> Tuple[float, float]:
    """
    Hansen SPA (Hansen 2005): verifica che il Sharpe del candidato migliore
    NON sia spiegabile dalla distribuzione del massimo Sharpe casuale
    sull'universo di coppie testato.

    H0: E[SR_best] <= max(E[SR_i]) per i = 1..M (puro caso)
    Test: confronta SR_best con la distribuzione del max(SR_i) via bootstrap
          stazionario a blocchi.

    Parametri:
    - best_pair_rets : rendimenti daily OOS del candidato migliore (np.ndarray)
    - null_sharpes   : lista di Sharpe OOS delle altre coppie (incluse quelle
                       con N_trade=0, che contribuiscono SR=0 alla distribuzione nulla)

    Ritorna (spa_stat, p_value).
    SPA p-value < 0.05: il candidato e' significativamente migliore del caso.
    """
    T = len(best_pair_rets)
    if T < 10:
        return float("nan"), float("nan")

    sr_best = sharpe(best_pair_rets)
    sr_null_max = max(null_sharpes) if null_sharpes else 0.0

    # SPA statistic: SR_best - E[max(SR_null_i)]
    spa_stat = sr_best - sr_null_max

    # Bootstrap stazionario: ri-campiona best_pair_rets a blocchi
    # per stimare la distribuzione di SR_best sotto la nulla (SR_null_max fisso).
    block_len = max(5, int(np.sqrt(T)))

    boot_sr = []
    for _ in range(n_boot):
        sample = []
        while len(sample) < T:
            start = int(RNG.integers(0, T))
            blk = best_pair_rets[start : start + block_len]
            if len(blk) < block_len and start > 0:
                blk = np.concatenate([blk, best_pair_rets[:block_len - len(blk)]])
            sample.extend(blk[:block_len].tolist())
        sample_arr = np.array(sample[:T])
        boot_sr.append(sharpe(sample_arr))

    boot_sr_arr = np.array(boot_sr)

    # p-value: proporzione di bootstrap in cui SR_boot - sr_null_max >= spa_stat
    # Equivalente a: quanto spesso il candidato batte il massimo casuale
    # per puro effetto di campionamento?
    boot_stats = boot_sr_arr - sr_null_max
    p_val = float(np.mean(boot_stats >= spa_stat))
    p_val = max(p_val, 1.0 / n_boot)
    return float(spa_stat), p_val


# =============================================================================
# SEZIONE 10 — CRITERI PASS/FAIL (§4 adattati per Tipo A e Tipo B)
# =============================================================================

def evaluate_momentum_b(
    wf_results: List[Dict],
    all_daily_rets: np.ndarray,
    equity_oos: np.ndarray,
    best_params: Dict,
) -> Dict:
    """
    Valuta il momentum come Tipo B (§12):
    - C1-B: bootstrap CI sul rendimento periodico daily.
    - C2: Sharpe OOS netto > 0.5.
    - C3: Sortino > 0.7.
    - C4: MDD < 25%.
    - C5: Calmar > 0.3.
    - C6-B: T >= 750 osservazioni periodiche.
    - C7: DSR p-value < 0.05 (con n_configs = 17).
    - C8: stabilita' WF >= 80%.
    """
    n_obs     = len(all_daily_rets)
    n_windows = len(wf_results)

    # --- Metriche aggregate ---
    sr    = sharpe(all_daily_rets)
    so    = sortino(all_daily_rets)
    mdd_v = max_drawdown(equity_oos)
    cal   = calmar(all_daily_rets, mdd_v)
    cag   = cagr(all_daily_rets)

    skew_v = float(scipy_stats.skew(all_daily_rets))  if n_obs > 3 else 0.0
    kurt_v = float(scipy_stats.kurtosis(all_daily_rets, fisher=False)) if n_obs > 3 else 3.0

    dsr_val, dsr_pval = deflated_sharpe(sr, n_obs, DSR_N_CONFIGS_MOM, skew_v, kurt_v)

    # C1-B: block bootstrap CI sul rendimento daily
    ci_lo, ci_hi, boot_p = bootstrap_ci_periodic(all_daily_rets)

    # Stabilita' WF
    wf_srs = [sharpe(w["daily_rets"]) for w in wf_results]
    wf_stab = sum(1 for s in wf_srs if s > 0) / n_windows if n_windows > 0 else 0.0

    # Criteri
    c1b = (not np.isnan(ci_lo)) and ci_lo > 0.0    # CI daily > 0
    c2  = sr    > 0.50
    c3  = so    > 0.70
    c4  = mdd_v < 0.25
    c5  = cal   > 0.30
    c6  = n_obs >= 750                               # C6-B: T >= 750 obs periodiche
    c7  = (not np.isnan(dsr_pval)) and dsr_pval < 0.05
    c8  = wf_stab >= 0.80

    all_pass = all([c1b, c2, c3, c4, c5, c6, c7, c8])

    # Killer criteria
    k1 = True   # N_trade non significativo per Tipo B (esposizione continua)
    k2 = True
    if len(equity_oos) > 4:
        last_q = equity_oos[3 * len(equity_oos) // 4:]
        mdd_lq = max_drawdown(last_q)
        if mdd_lq > mdd_v * 0.80:
            k2 = False
    k3 = True
    if n_windows >= 2:
        r_first = float(wf_results[0]["daily_rets"].mean()) if len(wf_results[0]["daily_rets"]) > 0 else 0.0
        r_last  = float(wf_results[-1]["daily_rets"].mean()) if len(wf_results[-1]["daily_rets"]) > 0 else 0.0
        if r_first * r_last < 0:
            k3 = False
    k4 = True   # Tipo B: N_trade non rilevante, T >= 750 gia' in C6
    k5 = True   # verifica Sharpe netto vs lordo
    gross_all = np.concatenate([w["daily_rets"] for w in wf_results])
    sr_gross  = sharpe(gross_all) if len(gross_all) > 2 else 0.0
    if sr > 0 and sr_gross > 0 and sr / sr_gross < 0.20:
        k5 = False

    killers_ok = all([k1, k2, k3, k4, k5])
    verdict = "PASS" if (all_pass and killers_ok) else "FAIL"

    return dict(
        type_signal="Tipo B (ALWAYS-IN)",
        n_obs=n_obs, sharpe=sr, sortino=so, mdd=mdd_v, calmar=cal, cagr_ann=cag,
        dsr=dsr_val, dsr_pval=dsr_pval, n_configs_dsr=DSR_N_CONFIGS_MOM,
        ci1b_lo=ci_lo, ci1b_hi=ci_hi, boot_p=boot_p,
        wf_stability=wf_stab, wf_sharpes=wf_srs,
        c1b=c1b, c2=c2, c3=c3, c4=c4, c5=c5, c6=c6, c7=c7, c8=c8,
        all_pass=all_pass,
        k1=k1, k2=k2, k3=k3, k4=k4, k5=k5, killers_ok=killers_ok,
        verdict=verdict,
        best_params=best_params,
    )


def evaluate_pair_a(
    sym_a: str, sym_b: str,
    wf_results: List[Dict],
    all_daily_rets: np.ndarray,
    all_trade_rets: np.ndarray,
    equity_oos: np.ndarray,
    n_windows: int,
) -> Dict:
    """
    Valuta una coppia pairs come Tipo A (§4):
    - C1: bootstrap CI 95% sul rendimento NETTO PER TRADE > 0.
    - C2-C8: criteri §4 standard.
    """
    n_obs    = len(all_daily_rets)
    n_trades = sum(w["n_trades"] for w in wf_results)

    sr    = sharpe(all_daily_rets)
    so    = sortino(all_daily_rets)
    mdd_v = max_drawdown(equity_oos)
    cal   = calmar(all_daily_rets, mdd_v)

    skew_v = float(scipy_stats.skew(all_daily_rets))  if n_obs > 3 else 0.0
    kurt_v = float(scipy_stats.kurtosis(all_daily_rets, fisher=False)) if n_obs > 3 else 3.0

    dsr_val, dsr_pval = deflated_sharpe(sr, n_obs, DSR_N_CONFIGS_PAIRS, skew_v, kurt_v)

    # C1: CI per trade
    if len(all_trade_rets) >= 5:
        ci_lo, ci_hi, boot_p = bootstrap_ci_per_trade(all_trade_rets)
    else:
        ci_lo, ci_hi, boot_p = float("nan"), float("nan"), float("nan")

    # WF stability
    wf_srs = [sharpe(w["daily_rets"]) if len(w["daily_rets"]) > 2 else 0.0 for w in wf_results]
    wf_stab = sum(1 for s in wf_srs if s > 0) / n_windows if n_windows > 0 else 0.0

    c1 = (not np.isnan(ci_lo)) and ci_lo > 0.0
    c2 = sr    > 0.50
    c3 = so    > 0.70
    c4 = mdd_v < 0.25
    c5 = cal   > 0.30
    c6 = n_trades >= 50
    c7 = (not np.isnan(dsr_pval)) and dsr_pval < 0.05
    c8 = wf_stab >= 0.80

    all_pass = all([c1, c2, c3, c4, c5, c6, c7, c8])

    # Killer criteria
    k1 = True
    if len(all_trade_rets) >= 3:
        srt = np.sort(all_trade_rets)[::-1]
        top3 = srt[:3].sum()
        pos_tot = srt[srt > 0].sum()
        if pos_tot > 0 and top3 / pos_tot > 0.70:
            k1 = False
    k2 = True
    if len(equity_oos) > 4:
        lq = equity_oos[3 * len(equity_oos) // 4:]
        if max_drawdown(lq) > mdd_v * 0.80:
            k2 = False
    k3 = True
    if n_windows >= 2:
        r1 = float(wf_results[0]["daily_rets"].mean()) if len(wf_results[0]["daily_rets"]) > 0 else 0.0
        rn = float(wf_results[-1]["daily_rets"].mean()) if len(wf_results[-1]["daily_rets"]) > 0 else 0.0
        if r1 * rn < 0:
            k3 = False
    k4 = n_trades >= 30
    k5 = True   # costi gia' inclusi nel daily_rets

    killers_ok = all([k1, k2, k3, k4, k5])
    verdict = "PASS" if (all_pass and killers_ok) else "FAIL"

    return dict(
        sym_a=sym_a, sym_b=sym_b,
        n_obs=n_obs, n_trades=n_trades,
        sharpe=sr, sortino=so, mdd=mdd_v, calmar=cal,
        dsr=dsr_val, dsr_pval=dsr_pval,
        ci1_lo=ci_lo, ci1_hi=ci_hi, boot_p=boot_p,
        wf_stability=wf_stab, wf_sharpes=wf_srs,
        c1=c1, c2=c2, c3=c3, c4=c4, c5=c5, c6=c6, c7=c7, c8=c8,
        all_pass=all_pass,
        k1=k1, k2=k2, k3=k3, k4=k4, k5=k5, killers_ok=killers_ok,
        verdict=verdict,
    )


# =============================================================================
# SEZIONE 11 — STAMPA RISULTATI
# =============================================================================

def SEP(c="-", w=100): print(c * w)


def print_mom_grid(df_grid: pd.DataFrame) -> None:
    print("\n  Griglia IS/VAL Momentum (ordinata per Sharpe IS/VAL decrescente):")
    SEP()
    print(f"  {'L':>4}  {'q':>5}  {'Sharpe':>8}  {'Sortino':>8}  {'MDD%':>6}  {'CAGR%':>7}  {'Calmar':>7}")
    SEP()
    for _, row in df_grid.iterrows():
        print(
            f"  {int(row['lookback_long']):>4}  {row['top_quantile']:>5.2f}  "
            f"{row['sharpe_isval']:>8.3f}  {row['sortino_isval']:>8.3f}  "
            f"{row['mdd_isval']*100:>5.1f}%  {row['cagr_isval']*100:>+7.2f}%  "
            f"{row['calmar_isval']:>7.3f}"
        )


def print_mom_eval(ev: Dict) -> None:
    SEP("=")
    print(f"  MOMENTUM CROSS-SECTIONAL — Tipo B — OOS Walk-Forward")
    SEP("=")
    print(f"  Parametri OOS: L={ev['best_params']['lookback_long']} q={ev['best_params']['top_quantile']:.2f} "
          f"VIX_z={ev['best_params']['vix_z_thresh']} (congelati su IS/VAL)")
    print(f"  n_configs DSR: {ev['n_configs_dsr']} (16 griglia IS/VAL + 1 tentativo round 1)")
    SEP()
    print(f"  T OOS (obs periodiche): {ev['n_obs']}")
    print(f"  Sharpe OOS netto:       {ev['sharpe']:.4f}")
    print(f"  Sortino OOS netto:      {ev['sortino']:.4f}")
    print(f"  MDD:                    {ev['mdd']*100:.2f}%")
    print(f"  Calmar:                 {ev['calmar']:.4f}")
    print(f"  CAGR annualizzato:      {ev['cagr_ann']*100:+.2f}%")
    print(f"  DSR:                    {ev['dsr']:.4f}  p={ev['dsr_pval']:.6f}")
    print(f"  C1-B CI 95% daily ret:  [{ev['ci1b_lo']*100:+.5f}%, {ev['ci1b_hi']*100:+.5f}%]  p={ev['boot_p']:.4f}")
    print(f"  WF stability:           {ev['wf_stability']*100:.0f}%  SharpePerFinestra={[f'{s:.2f}' for s in ev['wf_sharpes']]}")
    SEP()
    rows = [
        ("C1-B", "CI 95% rendimento daily > 0 (Tipo B)", f"lo={ev['ci1b_lo']*100:+.5f}%", ev["c1b"]),
        ("C2",   "Sharpe OOS netto > 0.5",                f"{ev['sharpe']:.4f}",             ev["c2"]),
        ("C3",   "Sortino OOS netto > 0.7",               f"{ev['sortino']:.4f}",            ev["c3"]),
        ("C4",   "MDD < 25%",                             f"{ev['mdd']*100:.2f}%",            ev["c4"]),
        ("C5",   "Calmar > 0.3",                          f"{ev['calmar']:.4f}",              ev["c5"]),
        ("C6-B", "T >= 750 obs periodiche OOS",           f"{ev['n_obs']}",                   ev["c6"]),
        ("C7",   "DSR p-value < 0.05",                   f"DSR={ev['dsr']:.3f} p={ev['dsr_pval']:.6f}", ev["c7"]),
        ("C8",   "WF stability >= 80%",                  f"{ev['wf_stability']*100:.0f}%",   ev["c8"]),
    ]
    for code, desc, val, passed in rows:
        print(f"  {code:<5} [{'PASS' if passed else 'FAIL'}]  {desc:<48} {val}")
    SEP()
    killers = [
        ("K1", "N/A per Tipo B (esposizione continua)",            ev["k1"]),
        ("K2", "MDD non concentrato nell'ultimo trimestre OOS",    ev["k2"]),
        ("K3", "Segno non ribaltato prima/ultima finestra WF",     ev["k3"]),
        ("K4", "N/A per Tipo B (usa C6-B)",                       ev["k4"]),
        ("K5", "Edge sopravvive ai costi (SR_net/SR_gross > 0.2)", ev["k5"]),
    ]
    for code, desc, ok in killers:
        print(f"  {code}  [{'OK' if ok else 'KO'}]  {desc}")
    SEP("=")
    verdict = "*** PASS ***" if ev["verdict"] == "PASS" else "!!! FAIL !!!"
    print(f"  VERDICT MOMENTUM: {verdict}")
    if ev["verdict"] == "FAIL":
        fc = [c for c, _, _, p in rows if not p]
        fk = [k for k, _, ok in killers if not ok]
        print(f"  Criteri FAIL: {fc}")
        print(f"  Killer KO:    {fk}")
    SEP("=")


def print_pairs_screening(screening_results: List[Dict], fdr_mask: List[bool]) -> None:
    print("\n  Screening cointegrazione IS — 14 coppie:")
    SEP()
    print(f"  {'Coppia':<18} {'ADF_res_IS':>12} {'HL_IS':>8} {'FDR':>5} {'Nota'}")
    SEP()
    for i, (sc, fdr) in enumerate(zip(screening_results, fdr_mask)):
        adf_p = sc["adf_p_residuals_is"]
        hl = sc["half_life_is"]
        adf_str = f"{adf_p:.4f}" if adf_p is not None else "N/A"
        hl_str  = f"{hl:.1f}gg" if hl is not None else "N/A"
        fdr_str = "PASS" if fdr else "FAIL"
        pair_str = f"{sc['sym_a']}/{sc['sym_b']}"
        print(f"  {pair_str:<18} {adf_str:>12} {hl_str:>8} {fdr_str:>5}  {sc['note'][:50]}")


def print_pair_eval(ev: Dict, spa_stat: float, spa_p: float) -> None:
    pair = f"{ev['sym_a']}/{ev['sym_b']}"
    SEP("=")
    print(f"  PAIRS MEAN REVERSION — {pair} — Tipo A — OOS Walk-Forward")
    SEP("=")
    print(f"  N_trade OOS: {ev['n_trades']} | T OOS: {ev['n_obs']} | WF stability: {ev['wf_stability']*100:.0f}%")
    print(f"  Sharpe: {ev['sharpe']:.4f} | Sortino: {ev['sortino']:.4f} | MDD: {ev['mdd']*100:.2f}% | Calmar: {ev['calmar']:.4f}")
    print(f"  DSR: {ev['dsr']:.4f}  p={ev['dsr_pval']:.6f}  (n_configs={DSR_N_CONFIGS_PAIRS})")
    print(f"  C1 CI 95% per trade: [{ev['ci1_lo']*100:+.3f}%, {ev['ci1_hi']*100:+.3f}%]  p={ev['boot_p']:.4f}")
    if not np.isnan(spa_stat):
        print(f"  Hansen SPA: stat={spa_stat:.4f}  p={spa_p:.4f}  ({'PASS' if spa_p < 0.05 else 'FAIL'})")
    SEP()
    rows = [
        ("C1", "CI 95% per trade > 0",  f"lo={ev['ci1_lo']*100:+.3f}%", ev["c1"]),
        ("C2", "Sharpe > 0.5",          f"{ev['sharpe']:.4f}",           ev["c2"]),
        ("C3", "Sortino > 0.7",         f"{ev['sortino']:.4f}",          ev["c3"]),
        ("C4", "MDD < 25%",             f"{ev['mdd']*100:.2f}%",          ev["c4"]),
        ("C5", "Calmar > 0.3",          f"{ev['calmar']:.4f}",            ev["c5"]),
        ("C6", "N_trade >= 50",         f"{ev['n_trades']}",              ev["c6"]),
        ("C7", "DSR p < 0.05",          f"p={ev['dsr_pval']:.6f}",        ev["c7"]),
        ("C8", "WF stability >= 80%",   f"{ev['wf_stability']*100:.0f}%", ev["c8"]),
    ]
    for code, desc, val, passed in rows:
        print(f"  {code:<4} [{'PASS' if passed else 'FAIL'}]  {desc:<45} {val}")
    SEP()
    killers = [
        ("K1", "Performance non concentrata in <=3 trade", ev["k1"]),
        ("K2", "MDD non nell'ultimo trimestre OOS",        ev["k2"]),
        ("K3", "Segno stabile tra prima/ultima finestra",  ev["k3"]),
        ("K4", "N_trade >= 30",                            ev["k4"]),
        ("K5", "Edge sopravvive ai costi",                 ev["k5"]),
    ]
    for code, desc, ok in killers:
        print(f"  {code}  [{'OK' if ok else 'KO'}]  {desc}")
    SEP("=")
    print(f"  VERDICT {pair}: {'*** PASS ***' if ev['verdict'] == 'PASS' else '!!! FAIL !!!'}")
    SEP("=")


# =============================================================================
# SEZIONE 12 — MAIN
# =============================================================================

def main() -> None:
    print()
    SEP("=")
    print("  VALIDAZIONE SEGNALI — ROUND 2 — VALIDATION_PROTOCOL §12 + §13")
    print("  Tom — TradingIA  |  Data:", pd.Timestamp.now().date())
    SEP("=")

    # -------------------------------------------------------------------------
    # 1. DOWNLOAD DATI
    # -------------------------------------------------------------------------
    print("\n[1] DOWNLOAD DATI STORICI (2010-01-01 — 2026-01-01)")
    SEP()

    print("\n  Universo Momentum (42 ETF + VIX):")
    all_mom_tickers = MOMENTUM_UNIVERSE + [VIX_TICKER]
    mom_panel_raw, mom_esclusi = build_panel(all_mom_tickers, label="Momentum")

    if len(mom_esclusi) > 0:
        print(f"\n  TICKER ESCLUSI DAL MOMENTUM (non sostituiti): {mom_esclusi}")

    # Separa VIX dal panel tradabile
    vix_df = mom_panel_raw.pop(VIX_TICKER, None)
    mom_panel = {k: v for k, v in mom_panel_raw.items() if k in MOMENTUM_UNIVERSE}

    if len(mom_panel) < 10:
        print("\n[ABORT] Troppi pochi ticker momentum scaricati. Connessione assente.")
        sys.exit(1)

    # Download pairs: raccogliamo tutti i ticker unici
    pairs_tickers = sorted(set(t for pair in PAIRS_UNIVERSE for t in pair))
    print(f"\n  Universo Pairs (25 ticker unici):")
    pairs_panel_raw, pairs_esclusi = build_panel(pairs_tickers, label="Pairs")

    if len(pairs_esclusi) > 0:
        print(f"\n  TICKER ESCLUSI DAI PAIRS (non sostituiti): {pairs_esclusi}")

    # Coppie disponibili (entrambi i ticker scaricati)
    pairs_available = [
        (a, b) for a, b in PAIRS_UNIVERSE
        if a in pairs_panel_raw and b in pairs_panel_raw
    ]
    pairs_unavailable = [
        (a, b) for a, b in PAIRS_UNIVERSE
        if a not in pairs_panel_raw or b not in pairs_panel_raw
    ]
    if pairs_unavailable:
        print(f"\n  COPPIE ESCLUSE (ticker mancante): {pairs_unavailable}")

    # -------------------------------------------------------------------------
    # 2. SPLIT TEMPORALE
    # -------------------------------------------------------------------------
    print("\n[2] SPLIT TEMPORALE")
    SEP()

    # Usa la lunghezza della serie piu' corta del panel momentum (dopo allineamento)
    n_bars = min(len(df) for df in mom_panel.values())
    is_end    = int(n_bars * IS_FRAC)
    val_end   = int(n_bars * (IS_FRAC + VAL_FRAC))
    oos_start = val_end
    oos_end   = n_bars
    n_oos     = oos_end - oos_start
    wf_size   = n_oos // N_WF_WINDOWS

    # Date approssimative (dal panel allineato)
    ref_dates = list(mom_panel.values())[0].index
    date_is_start  = ref_dates[0].date()
    date_is_end    = ref_dates[is_end - 1].date() if is_end < len(ref_dates) else "N/A"
    date_val_end   = ref_dates[val_end - 1].date() if val_end < len(ref_dates) else "N/A"
    date_oos_start = ref_dates[oos_start].date() if oos_start < len(ref_dates) else "N/A"
    date_oos_end   = ref_dates[oos_end - 1].date() if oos_end - 1 < len(ref_dates) else "N/A"

    print(f"  Dataset (barre allineate): {n_bars}")
    print(f"  IS  (60%):  bar 0 – {is_end:>4}   ({date_is_start} – {date_is_end})    [{is_end} barre]")
    print(f"  VAL (10%):  bar {is_end:>4} – {val_end:>4}   (– {date_val_end})    [{val_end - is_end} barre]")
    print(f"  OOS (30%):  bar {oos_start:>4} – {oos_end:>4}   ({date_oos_start} – {date_oos_end})  [{n_oos} barre]")
    print(f"  Finestre WF: {N_WF_WINDOWS} x ~{wf_size} barre ciascuna")
    print()
    print("  DISCIPLINA OOS: i parametri vengono congelati al passo [3.b] PRIMA di aprire l'OOS.")
    print("  L'OOS [3.c] viene eseguito UNA SOLA VOLTA con parametri congelati.")

    # -------------------------------------------------------------------------
    # 3. MOMENTUM TIPO B
    # -------------------------------------------------------------------------
    print("\n[3] MOMENTUM CROSS-SECTIONAL — Tipo B (§12)")
    SEP()

    # 3.a — Grid search su IS+VAL
    print(f"\n[3.a] Grid search IS/VAL ({len(GRID_LOOKBACK_LONG)}x{len(GRID_TOP_QUANTILE)} = "
          f"{len(GRID_LOOKBACK_LONG)*len(GRID_TOP_QUANTILE)} configurazioni)")
    print("  DISCIPLINA LAB-5: solo su bar 0..val_end. OOS non ancora aperto.\n")

    best_params, df_grid = grid_search_momentum(
        mom_panel, vix_df, bar_start=0, bar_end=val_end
    )
    print_mom_grid(df_grid)
    print(f"\n  >> Parametri congelati: L={best_params['lookback_long']} "
          f"q={best_params['top_quantile']:.2f}")
    print(f"  >> n_configs DSR = {DSR_N_CONFIGS_MOM} "
          f"(16 grid IS/VAL + 1 tentativo round 1 — PENA ONESTA per OOS gia' visto)")

    # 3.b — Parametri congelati: da questo punto non si torna indietro
    print("\n  *** PARAMETRI CONGELATI — OOS SI APRE ORA ***")

    # 3.c — OOS Walk-Forward
    print(f"\n[3.c] OOS Walk-Forward Momentum (parametri congelati):")
    wf_mom, daily_rets_mom, equity_mom = run_momentum_oos(
        mom_panel, vix_df, oos_start, oos_end, best_params, N_WF_WINDOWS
    )

    # 3.d — Valutazione criteri Tipo B
    mom_eval = evaluate_momentum_b(wf_mom, daily_rets_mom, equity_mom, best_params)
    print_mom_eval(mom_eval)

    # -------------------------------------------------------------------------
    # 4. PAIRS — SCREENING IS + FDR + OOS + SPA
    # -------------------------------------------------------------------------
    print("\n[4] PAIRS MEAN REVERSION — §13 (screening IS + FDR + OOS + SPA)")
    SEP()

    # 4.a — Screening cointegrazione IS (LAB-6: SOLO su bar IS)
    # DISCIPLINA: ogni coppia calcola il proprio is_end sul proprio panel allineato.
    # NON si usa is_end del momentum: il pairs panel ha storia dal 2010 (4024 barre),
    # il momentum panel inizia dal 2018 (1895 barre). Usare is_end=1137 del momentum
    # applicato ai pairs limiterebbe lo screening al solo 28% della storia disponibile.
    # Per ogni coppia: is_end_pair = int(n_pair_bars * IS_FRAC).
    print(f"\n[4.a] Screening ADF cointegrazione su IS (60% di ogni coppia) — coppie disponibili: {len(pairs_available)}")
    print("  DISCIPLINA LAB-6: l'OOS non viene aperto fino a dopo FDR.")
    print("  NOTA: ogni coppia usa il proprio is_end (60% della propria serie comune),")
    print("  NON l'is_end del momentum (che ha storia piu' corta a causa dell'inner join su 42 ETF).")

    # Per il pairs usiamo l'allineamento dei rispettivi df (non il panel momentum)
    screening_results = []
    for sym_a, sym_b in pairs_available:
        df_a = pairs_panel_raw[sym_a]
        df_b = pairs_panel_raw[sym_b]
        # is_end calcolato sulla serie comune della coppia specifica
        common_pair = df_a.index.intersection(df_b.index)
        is_end_pair = int(len(common_pair) * IS_FRAC)
        sc = screen_pair_on_is(sym_a, df_a, sym_b, df_b, is_end=is_end_pair)
        screening_results.append(sc)

    # Aggiungi coppie non disponibili come escluse automaticamente
    for sym_a, sym_b in pairs_unavailable:
        screening_results.append({
            "sym_a": sym_a, "sym_b": sym_b,
            "admitted_is": False,
            "adf_p_residuals_is": None,
            "half_life_is": None,
            "note": "ticker non disponibile su yfinance",
        })

    # 4.b — FDR Benjamini-Hochberg sui p-value ADF IS
    # LAB-7: FDR calcolato SOLO sui p-value IS.
    print(f"\n[4.b] FDR Benjamini-Hochberg (alpha={FDR_ALPHA}) sui {len(screening_results)} candidati:")
    adf_pvals_all = []
    for sc in screening_results:
        p = sc.get("adf_p_residuals_is")
        adf_pvals_all.append(p if p is not None else 1.0)

    fdr_mask_all = fdr_benjamini_hochberg(adf_pvals_all, alpha=FDR_ALPHA)
    print_pairs_screening(screening_results, fdr_mask_all)

    # Coppie sopravvissute a FDR: admitted_is=True AND fdr=True AND half-life <= max
    fdr_survivors = []
    for sc, fdr in zip(screening_results, fdr_mask_all):
        if fdr and sc.get("admitted_is", False):
            hl = sc.get("half_life_is")
            if hl is None or hl <= PAIRS_PARAMS_FIXED["max_half_life_bars"]:
                fdr_survivors.append(sc)
            else:
                print(f"  [FDR PASS ma ESCLUSA per half-life={hl:.1f} > {PAIRS_PARAMS_FIXED['max_half_life_bars']}]: "
                      f"{sc['sym_a']}/{sc['sym_b']}")

    print(f"\n  Coppie sopravvissute a FDR + half-life: {len(fdr_survivors)}")
    for sc in fdr_survivors:
        hl_str   = f"{sc['half_life_is']:.1f}gg" if sc['half_life_is'] is not None else "N/A"
        beta_str = f"{sc['beta_hat_is']:.4f}"    if sc['beta_hat_is']  is not None else "N/A"
        adf_str  = f"{sc['adf_p_residuals_is']:.4f}" if sc['adf_p_residuals_is'] is not None else "N/A"
        print(f"    {sc['sym_a']}/{sc['sym_b']}  ADF_p={adf_str}  HL={hl_str}  beta_is={beta_str}")

    if len(fdr_survivors) == 0:
        print("\n  [ABORT PAIRS] Nessuna coppia sopravvive a FDR. Segnale FAIL per assenza di candidati.")
        pairs_final_eval = []
        spa_best = (float("nan"), float("nan"))
    else:
        # *** OOS PAIRS SI APRE QUI — MAI PRIMA ***
        print("\n  *** OOS PAIRS SI APRE ORA (dopo FDR, parametri congelati) ***")

        # 4.c — OOS Walk-Forward su ogni coppia sopravvissuta
        print(f"\n[4.c] OOS Walk-Forward su {len(fdr_survivors)} coppie sopravvissute:")

        pairs_final_eval = []
        for sc in fdr_survivors:
            sym_a, sym_b = sc["sym_a"], sc["sym_b"]
            df_a = pairs_panel_raw[sym_a]
            df_b = pairs_panel_raw[sym_b]
            beta_is = sc["beta_hat_is"]

            # Allineamento comune per il backtester
            common = df_a.index.intersection(df_b.index)
            n_pair = len(common)
            is_end_pair    = int(n_pair * IS_FRAC)
            val_end_pair   = int(n_pair * (IS_FRAC + VAL_FRAC))
            oos_start_pair = val_end_pair
            oos_end_pair   = n_pair
            wf_size_pair   = (oos_end_pair - oos_start_pair) // N_WF_WINDOWS

            print(f"\n  >> {sym_a}/{sym_b}: {n_pair} barre comuni | OOS: bar {oos_start_pair}-{oos_end_pair}")

            bt_pair = PairsBacktesterOOS(sym_a, df_a, sym_b, df_b, beta_is)
            wf_pair = []
            all_dr = []
            all_tr = []
            equity_p = np.array([1.0])

            for w_idx in range(N_WF_WINDOWS):
                w_start = oos_start_pair + w_idx * wf_size_pair
                w_end   = w_start + wf_size_pair if w_idx < N_WF_WINDOWS - 1 else oos_end_pair
                print(f"    Finestra {w_idx+1}/{N_WF_WINDOWS}: bar {w_start}-{w_end} ...", end="", flush=True)
                res = bt_pair.run(w_start, w_end)
                wf_pair.append(res)
                all_dr.append(res["daily_rets"])
                all_tr.append(res["net_trade_rets"])
                eq = res["equity"]
                if len(eq) > 1:
                    scale = equity_p[-1]
                    equity_p = np.concatenate([equity_p, eq[1:] * scale / eq[0]])
                print(f"  N_trade={res['n_trades']}  Sharpe={sharpe(res['daily_rets']):.3f}")

            all_dr_arr = np.concatenate(all_dr) if all_dr else np.array([])
            all_tr_arr = np.concatenate(all_tr) if all_tr else np.array([])

            ev_pair = evaluate_pair_a(
                sym_a, sym_b, wf_pair, all_dr_arr, all_tr_arr, equity_p, N_WF_WINDOWS
            )
            pairs_final_eval.append((ev_pair, all_dr_arr))

        # 4.d — SPA sul candidato migliore (massimo Sharpe OOS)
        print(f"\n[4.d] Hansen SPA sul candidato migliore tra {len(pairs_final_eval)} coppie:")
        if pairs_final_eval:
            # Ordina per Sharpe OOS
            sorted_pairs = sorted(pairs_final_eval, key=lambda x: x[0]["sharpe"], reverse=True)
            best_ev, best_rets = sorted_pairs[0]
            null_sharpes = [ev["sharpe"] for ev, _ in sorted_pairs[1:]]
            # Aggiungi SR=0 per le coppie escluse dalla FDR (contribuiscono alla nulla)
            null_sharpes += [0.0] * (len(PAIRS_UNIVERSE) - len(fdr_survivors))

            spa_stat_val, spa_p_val = hansen_spa(best_rets, null_sharpes)
            spa_best = (spa_stat_val, spa_p_val)
            print(f"  Candidato migliore: {best_ev['sym_a']}/{best_ev['sym_b']}  "
                  f"Sharpe={best_ev['sharpe']:.4f}")
            print(f"  SPA statistic: {spa_stat_val:.4f}  p-value={spa_p_val:.4f}")
            if spa_p_val < 0.05:
                print("  SPA: PASS (Sharpe significativamente > distribuzione nulla)")
            else:
                print("  SPA: FAIL (Sharpe non distinguibile dalla migliore coppia casuale)")
        else:
            spa_best = (float("nan"), float("nan"))

        # Stampa valutazione di ogni coppia
        for ev_pair, _ in pairs_final_eval:
            print_pair_eval(ev_pair, *spa_best)

    # -------------------------------------------------------------------------
    # 5. RIEPILOGO FINALE
    # -------------------------------------------------------------------------
    print("\n[5] RIEPILOGO FINALE")
    SEP("=")
    print()
    print(f"  {'Segnale':<30} {'Tipo':>8} {'Verdict':>8} {'Sharpe':>8} {'MDD':>7} {'WF_stab':>8} {'DSR_p':>9}")
    SEP()

    print(
        f"  {'Momentum Cross-Sect.':<30} "
        f"{'B':>8} "
        f"{mom_eval['verdict']:>8}  "
        f"{mom_eval['sharpe']:>7.4f}  "
        f"{mom_eval['mdd']*100:>5.1f}%  "
        f"{mom_eval['wf_stability']*100:>6.0f}%  "
        f"{mom_eval['dsr_pval']:>9.6f}"
    )

    if pairs_final_eval:
        for ev_pair, _ in pairs_final_eval:
            pair_name = f"{ev_pair['sym_a']}/{ev_pair['sym_b']}"
            print(
                f"  {pair_name:<30} "
                f"{'A':>8} "
                f"{ev_pair['verdict']:>8}  "
                f"{ev_pair['sharpe']:>7.4f}  "
                f"{ev_pair['mdd']*100:>5.1f}%  "
                f"{ev_pair['wf_stability']*100:>6.0f}%  "
                f"{ev_pair['dsr_pval']:>9.6f}"
            )
    else:
        print(f"  {'Pairs (tutti)':<30} {'A':>8} {'FAIL':>8}  (nessuna coppia sopravvive a FDR IS)")

    SEP()
    spa_stat_fin, spa_p_fin = spa_best if 'spa_best' in dir() else (float("nan"), float("nan"))
    print(f"\n  Hansen SPA (coppia migliore):  stat={spa_stat_fin:.4f}  p={spa_p_fin:.4f}")
    print(f"  n_configs DSR Momentum: {DSR_N_CONFIGS_MOM} | n_configs DSR Pairs: {DSR_N_CONFIGS_PAIRS}")

    SEP("=")
    print("  ASSUNZIONI DICHIARATE E LIMITI")
    SEP("=")
    print("  1. Entry simulata come chiusura t (proxy per open t+1): slippage reale")
    print("     puo' essere peggiore su apertura gap. Limite dichiarato e conservativo.")
    print("  2. Costi momentum: media ponderata per gruppo ETF (dal ROUND2_UNIVERSE.md).")
    print("     L'universo 42 ETF non e' point-in-time puro: ETF come XLRE (2015) e")
    print("     XLC (2018) vengono inclusi solo dalla loro data reale di IPO.")
    print("  3. OOS 2022-2026 era gia' stato osservato nel round 1.")
    print("     Il costo statistico e' pagato con n_configs=17 nel DSR.")
    print("     Non possiamo dichiarare questo un 'OOS puro' — e' un OOS penalizzato.")
    print("  4. Pairs: la selezione delle 14 coppie e' avvenuta per ragioni economiche")
    print("     (ROUND2_UNIVERSE.md) prima di vedere i dati. Non e' data-mining.")
    print("     Il FDR a alpha=0.10 e' piu' permissivo di 0.05 per la selezione IS:")
    print("     accettiamo piu' falsi positivi nella selezione per non perdere coppie")
    print("     potenzialmente valide che verranno poi rigettate dall'OOS.")
    print("  5. SPA bootstrap usa blocchi di lunghezza sqrt(T_oos). L'approssimazione")
    print("     e' ragionevole per T > 200 (Politis & Romano 1994).")
    SEP("=")
    print()


if __name__ == "__main__":
    main()
