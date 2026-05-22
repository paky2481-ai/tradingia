"""
MomentumCrossSectionalSignal — implementazione completa.

Matematica (VALIDATION_PROTOCOL §1, Segnale A)
-----------------------------------------------
Mom_adj(i, t) = P(i, t-S) / P(i, t-L) - 1

  S = lookback_skip  : barre recenti da escludere per neutralizzare la mean-reversion
                       di brevissimo termine (Jegadeesh-Titman 1993: skip 1 mese).
  L = lookback_long  : finestra lunga del momentum (default 252 barre daily = ~1 anno).

La formula usa i PREZZI PASSATI, non il prezzo corrente: P(t-S) è la chiusura di S
barre fa, P(t-L) è la chiusura di L barre fa.  Il valore a barra t NON entra nel
calcolo, eliminando il look-ahead bias documentato in §6 regola 4.

Ranking:
  - Rank lineare cross-sectional di Mom_adj → percentile p_i ∈ [0, 1]
  - Score_i = 2 * p_i - 1  →  [-1, +1]
  - Soglia di attivazione: solo le "code" del ranking generano segnale
    (i.e. |score| >= soglia derivata da top_quantile)

Filtro regime VIX:
  - z_vix(t) = (VIX(t) - mu_rolling(t)) / sigma_rolling(t)
    con mu e sigma calcolati su finestra vix_window CHIUSA alla barra t-1
    (non include t: altrimenti sarebbe VIX contemporaneo all'ingresso, bias §6 regola 3).
  - Se z_vix(t) >= vix_z_threshold: tutti gli score → 0.0 (regime "panic").

La VIX series viene cercata in data["VIX"] (key standard) o nell'attributo
df.attrs["vix_series"] su qualsiasi membro del panel.

Look-ahead bias check:
  - mom_adj usa solo P(t-S) e P(t-L): entrambi rigorosamente nel passato.
  - VIX z-score usa rolling con min_periods e .shift(1) per escludere il bar corrente.
  - Il ranking è calcolato sull'ultima riga disponibile nel panel (riga -1), quindi
    sulla barra corrente che include i dati fino alla chiusura del giorno.
    ATTENZIONE: il signal compute() deve essere chiamato DOPO la chiusura della barra
    (mai in intraday), e l'esecuzione avviene alla barra+1 (open successivo).
    Il validate_signals.py rispetta questo vincolo con il lag esplicito.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

from strategies.signal_base import (
    ParamSpec,
    Signal,
    SignalCategory,
    SignalOutput,
    SignalScope,
)

logger = logging.getLogger("strategies.signals.momentum_cross_sectional")

# Minimo numero di asset nel panel per rendere il ranking significativo.
# Con N < MIN_UNIVERSE il percentile non ha potenza statistica.
_MIN_UNIVERSE = 5


class MomentumCrossSectionalSignal(Signal):
    """
    Cross-sectional momentum ranking signal (VALIDATION_PROTOCOL §1, Segnale A).

    Riceve un panel Dict[symbol, OHLCV DataFrame] e restituisce un SignalOutput
    per ogni asset, con score in [-1, +1] derivato dal rank del momentum aggiustato.
    """

    signal_id       = "momentum_cross_sectional"
    label           = "Momentum Cross-Sectional"
    scope           = SignalScope.CROSS_ASSET
    category        = SignalCategory.MOMENTUM
    default_weight  = 1.0
    # Abilitato a False per default: deve superare il §4 prima di essere attivato.
    default_enabled = False

    param_specs = [
        ParamSpec(
            "lookback_long", "int", 252, lo=60, hi=504,
            description="Barre per la finestra lunga del momentum (L)",
        ),
        ParamSpec(
            "lookback_skip", "int", 5, lo=1, hi=20,
            description="Barre recenti da escludere (skip, neutralizza mean-reversion)",
        ),
        ParamSpec(
            "top_quantile", "float", 0.2, lo=0.05, hi=0.5,
            description="Frazione dell'universo nelle gambe long/short",
        ),
        ParamSpec(
            "vix_z_threshold", "float", 2.0, lo=1.0, hi=4.0,
            description="z-score VIX sopra cui il segnale va a zero (regime panic)",
        ),
        ParamSpec(
            "vix_window", "int", 252, lo=60, hi=504,
            description="Finestra rolling per il z-score VIX",
        ),
    ]

    # ── Implementazione compute() ──────────────────────────────────────────────

    def compute(
        self,
        data: Dict[str, pd.DataFrame],
    ) -> List[SignalOutput]:
        """
        Calcola i segnali di momentum cross-sectional sull'intero panel.

        Parameters
        ----------
        data : Dict[symbol, OHLCV DataFrame]
            Ogni DataFrame deve avere colonna 'close' e DatetimeIndex.
            Il VIX è atteso sotto la chiave "VIX" nel panel, oppure come
            df.attrs["vix_series"] (pd.Series) su qualsiasi membro.

        Returns
        -------
        List[SignalOutput] — un elemento per asset (escluso "VIX").
        Lista vuota se il panel è insufficiente o il filtro VIX è attivo.
        """
        if not isinstance(data, dict):
            logger.error("MomentumCrossSectional: data deve essere un Dict[str, DataFrame]")
            return []

        # ── 1. Estrai VIX dal panel (non è un asset da tradare)
        vix_series: pd.Series | None = self._extract_vix(data)

        # ── 2. Filtra i simboli tradabili (esclude "VIX")
        symbols = [s for s in data.keys() if s.upper() != "VIX"]

        if len(symbols) < _MIN_UNIVERSE:
            logger.debug(
                "MomentumCrossSectional: universo troppo piccolo (%d < %d), skip",
                len(symbols), _MIN_UNIVERSE,
            )
            return []

        # ── 3. Controlla filtro VIX sul bar corrente
        # La z-score usa rolling su finestra chiusa a t-1 (.shift(1)) per evitare
        # il look-ahead documentato in §6 regola 3.
        if vix_series is not None and len(vix_series) > self.vix_window:
            # shift(1): esclude la chiusura corrente del VIX dal calcolo della media
            # => la z-score a t usa solo informazioni disponibili a t-1.
            roll = vix_series.shift(1).rolling(window=self.vix_window, min_periods=self.vix_window // 2)
            vix_mu    = roll.mean()
            vix_sigma = roll.std(ddof=1)
            last_vix  = vix_series.iloc[-1]
            last_mu   = float(vix_mu.iloc[-1])
            last_sig  = float(vix_sigma.iloc[-1])
            if last_sig > 0:
                z_vix = (last_vix - last_mu) / last_sig
                if z_vix >= self.vix_z_threshold:
                    logger.info(
                        "MomentumCrossSectional: VIX z=%.2f >= %.2f, segnale azzerato (regime panic)",
                        z_vix, self.vix_z_threshold,
                    )
                    # Ritorna flat per tutti gli asset (non lista vuota: il registry
                    # deve sapere che il segnale era attivo ma in flat).
                    return [
                        SignalOutput(
                            symbol=sym,
                            score=0.0,
                            confidence=0.0,
                            direction="flat",
                            metadata={"vix_z": round(float(z_vix), 3), "regime": "panic"},
                        )
                        for sym in symbols
                    ]

        # ── 4. Calcola Mom_adj per ogni asset
        # Mom_adj(i, t) = P(i, t-S) / P(i, t-L) - 1
        # P(t-S) = close S barre fa; P(t-L) = close L barre fa.
        # Usiamo .iloc[-1 - S] e .iloc[-1 - L]: rigorosamente nel passato,
        # mai il prezzo corrente (iloc[-1] = barra di chiusura corrente).
        L = self.lookback_long
        S = self.lookback_skip

        mom_values: dict[str, float] = {}

        for sym in symbols:
            df = data[sym]
            if "close" not in df.columns:
                logger.warning("MomentumCrossSectional: simbolo %s senza colonna 'close'", sym)
                continue
            n = len(df)
            # Serve almeno L+1 barre per ottenere P(t-L)
            if n < L + 1:
                logger.debug("MomentumCrossSectional: %s ha %d < %d barre, skip", sym, n, L + 1)
                continue
            # Indici negativi: -1 = ultima barra (corrente), -(S+1) = S barre fa.
            # Usando -(S+1): P(t-S) = close della barra chiusa S barre fa.
            p_skip = float(df["close"].iloc[-(S + 1)])   # P(t-S)
            p_long = float(df["close"].iloc[-(L + 1)])   # P(t-L)

            if p_long <= 0 or not np.isfinite(p_skip) or not np.isfinite(p_long):
                continue

            mom_values[sym] = p_skip / p_long - 1.0

        if len(mom_values) < _MIN_UNIVERSE:
            logger.debug(
                "MomentumCrossSectional: troppo pochi simboli con dati validi (%d)", len(mom_values)
            )
            return []

        # ── 5. Ranking cross-sectional → score in [-1, +1]
        # Rank percentile: p_i = rank_i / (N-1), con N = numero asset
        # Score lineare: score_i = 2 * p_i - 1  → [-1, +1]
        # Il rank è ASCENDING (momentum basso = rank basso = score negativo).
        sorted_syms = sorted(mom_values.keys(), key=lambda s: mom_values[s])
        n_ranked    = len(sorted_syms)
        rank_map    = {sym: i for i, sym in enumerate(sorted_syms)}  # 0 = peggiore

        # Soglia attivazione: |score| >= 1 - 2*top_quantile
        # Es. top_quantile=0.2 → score >= 0.6 per long, <= -0.6 per short
        activation_threshold = 1.0 - 2.0 * self.top_quantile

        outputs: List[SignalOutput] = []
        for sym in sorted_syms:
            rank_i     = rank_map[sym]
            percentile = rank_i / (n_ranked - 1) if n_ranked > 1 else 0.5
            score      = 2.0 * percentile - 1.0   # in [-1, +1]

            if abs(score) < activation_threshold:
                direction = "flat"
            elif score > 0:
                direction = "long"
            else:
                direction = "short"

            # Confidence: scala il valore assoluto dello score normalizzato
            # rispetto all'activation_threshold. 0 = appena in soglia, 1 = estremo.
            if abs(score) >= activation_threshold and activation_threshold < 1.0:
                raw_conf = (abs(score) - activation_threshold) / (1.0 - activation_threshold)
                confidence = float(np.clip(raw_conf, 0.0, 1.0))
            else:
                confidence = 0.0

            outputs.append(SignalOutput(
                symbol    = sym,
                score     = round(float(score), 4),
                confidence= round(confidence, 4),
                direction = direction,
                metadata  = {
                    "mom_adj":    round(float(mom_values[sym]), 6),
                    "rank":       rank_i,
                    "n_universe": n_ranked,
                    "percentile": round(float(percentile), 4),
                    "lookback_L": L,
                    "lookback_S": S,
                },
            ))

        return outputs

    # ── Utility ───────────────────────────────────────────────────────────────

    def _extract_vix(self, data: Dict[str, pd.DataFrame]) -> pd.Series | None:
        """
        Cerca il VIX nel panel.

        Priorità:
          1. data["VIX"]["close"]    — chiave standard
          2. data["^VIX"]["close"]   — ticker Yahoo Finance
          3. df.attrs["vix_series"]  — iniettato dal chiamante
        """
        for vix_key in ("VIX", "^VIX"):
            if vix_key in data:
                df_vix = data[vix_key]
                if "close" in df_vix.columns and len(df_vix) > 0:
                    return df_vix["close"].astype(float)

        # Fallback: cerca negli attrs di qualsiasi df del panel
        for df in data.values():
            vs = df.attrs.get("vix_series")
            if vs is not None and isinstance(vs, pd.Series) and len(vs) > 0:
                return vs.astype(float)

        return None
