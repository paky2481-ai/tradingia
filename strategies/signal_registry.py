"""
Signal Registry — composizione pesata di Signal in TradeSignal.

Il registry è il punto unico di registrazione e orchestrazione dei segnali
pluggabili definiti in signal_base.py.  Gestisce:

- Registrazione / rimozione dinamica di Signal
- Pesi e flag enabled per ogni segnale
- Dispatch per scope (PER_ASSET | CROSS_ASSET | PAIR)
- Formula ensemble pesata: score = Σ(wᵢ · scoreᵢ) / Σwᵢ  (solo enabled)
- Conversione finale SignalOutput → TradeSignal via SignalStrategy adapter
- Serializzazione / deserializzazione per QSettings (AppState)
- Notifica al SignalBus su modifiche (registry_changed, weight_updated)

Thread safety
-------------
Il registry è progettato per essere chiamato dal thread asyncio del motore
(come il StrategyManager).  Nessun lock interno: non usarlo da più thread
senza protezione esterna.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from strategies.base_strategy import TradeSignal
from strategies.signal_base import (
    Signal,
    SignalOutput,
    SignalScope,
    SignalStrategy,
)

logger = logging.getLogger("strategies.registry")

# Direzione ensemble: sopra questa soglia assoluta di score si genera un segnale.
_DEFAULT_SCORE_THRESHOLD = 0.25


class SignalRegistry:
    """
    Registro centrale dei segnali pluggabili.

    Uso tipico
    ----------
        registry = SignalRegistry()
        registry.register(MyRsiSignal(), weight=0.8)
        registry.register(MomentumSignal(), weight=1.2, enabled=False)

        # Per asset singolo (PER_ASSET / PAIR):
        signals = registry.compose_per_asset("EURUSD", df)

        # Per panel cross-sectional (CROSS_ASSET):
        signals = registry.compose_cross_asset(panel_dict)

        # Compose automatico (distiguisce scope):
        signals = registry.compose("EURUSD", df)
    """

    def __init__(
        self,
        score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
        default_timeframe: str = "1h",
    ) -> None:
        self._signals:  Dict[str, Signal]  = {}
        self._weights:  Dict[str, float]   = {}
        self._enabled:  Dict[str, bool]    = {}
        self._score_threshold = score_threshold
        self._default_timeframe = default_timeframe

    # ── Registrazione ─────────────────────────────────────────────────────────

    def register(
        self,
        signal: Signal,
        weight:  Optional[float] = None,
        enabled: Optional[bool]  = None,
    ) -> None:
        """
        Registra un segnale nel registry.

        Parameters
        ----------
        signal  : istanza concreta di Signal.
        weight  : peso ensemble (default: signal.default_weight).
        enabled : se attivo subito (default: signal.default_enabled).
        """
        if not signal.signal_id:
            raise ValueError(
                f"Signal {type(signal).__name__} must define a non-empty signal_id."
            )
        sid = signal.signal_id
        self._signals[sid]  = signal
        self._weights[sid]  = weight  if weight  is not None else signal.default_weight
        self._enabled[sid]  = enabled if enabled is not None else signal.default_enabled
        logger.info(
            "SignalRegistry: registered '%s' (scope=%s, weight=%.2f, enabled=%s)",
            sid, signal.scope.value, self._weights[sid], self._enabled[sid],
        )
        self._notify_registry_changed()

    def unregister(self, name: str) -> None:
        """Rimuove un segnale dal registry.  Silenzioso se non esiste."""
        if name in self._signals:
            del self._signals[name]
            del self._weights[name]
            del self._enabled[name]
            logger.info("SignalRegistry: unregistered '%s'", name)
            self._notify_registry_changed()

    # ── Configurazione runtime ─────────────────────────────────────────────────

    def set_weight(self, name: str, weight: float) -> None:
        if name not in self._signals:
            raise KeyError(f"Signal '{name}' not registered.")
        self._weights[name] = float(weight)
        logger.debug("SignalRegistry: weight '%s' → %.3f", name, weight)
        self._notify_weight_updated(name, weight)

    def set_enabled(self, name: str, enabled: bool) -> None:
        if name not in self._signals:
            raise KeyError(f"Signal '{name}' not registered.")
        self._enabled[name] = bool(enabled)
        logger.debug("SignalRegistry: enabled '%s' → %s", name, enabled)
        self._notify_registry_changed()

    # ── Introspezione ──────────────────────────────────────────────────────────

    def list_signals(self) -> List[Dict[str, Any]]:
        """
        Restituisce la lista dei segnali registrati con metadati completi.

        Usato dalla futura GUI per popolare il pannello di configurazione.
        """
        result = []
        for sid, signal in self._signals.items():
            meta = signal.registry_metadata()
            meta["weight"]  = self._weights[sid]
            meta["enabled"] = self._enabled[sid]
            result.append(meta)
        return result

    def get_signal(self, name: str) -> Optional[Signal]:
        return self._signals.get(name)

    def __len__(self) -> int:
        return len(self._signals)

    def __contains__(self, name: str) -> bool:
        return name in self._signals

    # ── Compose — entry point principale ──────────────────────────────────────

    def compose(
        self,
        data: Any,
        symbol: Optional[str] = None,
    ) -> List[TradeSignal]:
        """
        Calcola l'ensemble pesato e restituisce TradeSignal pronti per il Backtester.

        Dispatch automatico per scope:
        - Se `data` è una tuple (str, DataFrame) → PER_ASSET
        - Se `data` è un dict {str: DataFrame}    → CROSS_ASSET
        - Se `data` è una tuple di 4 (sym_a, df_a, sym_b, df_b) → PAIR

        Parameters
        ----------
        data   : vedi SignalScope per la struttura attesa.
        symbol : richiesto solo per PER_ASSET quando `data` è già un DataFrame
                 (convenience wrapper: passa (symbol, df) o il solo df + symbol=...).
        """
        # Normalizzazione ingresso conveniente
        if isinstance(data, pd.DataFrame) and symbol is not None:
            data = (symbol, data)

        if isinstance(data, dict):
            return self.compose_cross_asset(data)
        elif isinstance(data, tuple):
            if len(data) == 4:
                return self.compose_pair(*data)  # (sym_a, df_a, sym_b, df_b)
            elif len(data) == 2:
                sym, df = data
                return self.compose_per_asset(sym, df)
        raise TypeError(
            f"compose() received unsupported data type: {type(data).__name__}. "
            "Expected (symbol, df), {symbol: df}, or (sym_a, df_a, sym_b, df_b)."
        )

    def compose_per_asset(
        self,
        symbol: str,
        df: pd.DataFrame,
    ) -> List[TradeSignal]:
        """Ensemble dei segnali PER_ASSET su un singolo (symbol, OHLCV df)."""
        outputs_per_symbol: Dict[str, List[Tuple[SignalOutput, float]]] = {}

        for sid, signal in self._signals.items():
            if not self._enabled[sid]:
                continue
            if signal.scope != SignalScope.PER_ASSET:
                continue
            w = self._weights[sid]
            try:
                outs = signal.compute((symbol, df))
                for out in outs:
                    outputs_per_symbol.setdefault(out.symbol, []).append((out, w))
            except Exception as exc:
                logger.error("Signal '%s' compute error: %s", sid, exc)

        return self._ensemble_to_trade_signals(outputs_per_symbol)

    def compose_cross_asset(
        self,
        panel: Dict[str, pd.DataFrame],
    ) -> List[TradeSignal]:
        """Ensemble dei segnali CROSS_ASSET su un panel {symbol: OHLCV df}."""
        outputs_per_symbol: Dict[str, List[Tuple[SignalOutput, float]]] = {}

        for sid, signal in self._signals.items():
            if not self._enabled[sid]:
                continue
            if signal.scope != SignalScope.CROSS_ASSET:
                continue
            w = self._weights[sid]
            try:
                outs = signal.compute(panel)
                for out in outs:
                    outputs_per_symbol.setdefault(out.symbol, []).append((out, w))
            except Exception as exc:
                logger.error("Signal '%s' cross-asset compute error: %s", sid, exc)

        return self._ensemble_to_trade_signals(outputs_per_symbol)

    def compose_pair(
        self,
        sym_a: str,
        df_a:  pd.DataFrame,
        sym_b: str,
        df_b:  pd.DataFrame,
    ) -> List[TradeSignal]:
        """Ensemble dei segnali PAIR su una coppia di asset."""
        outputs_per_symbol: Dict[str, List[Tuple[SignalOutput, float]]] = {}

        for sid, signal in self._signals.items():
            if not self._enabled[sid]:
                continue
            if signal.scope != SignalScope.PAIR:
                continue
            w = self._weights[sid]
            try:
                outs = signal.compute((sym_a, df_a, sym_b, df_b))
                for out in outs:
                    outputs_per_symbol.setdefault(out.symbol, []).append((out, w))
            except Exception as exc:
                logger.error("Signal '%s' pair compute error: %s", sid, exc)

        return self._ensemble_to_trade_signals(outputs_per_symbol)

    # ── Logica ensemble ────────────────────────────────────────────────────────

    def _ensemble_to_trade_signals(
        self,
        outputs_per_symbol: Dict[str, List[Tuple[SignalOutput, float]]],
    ) -> List[TradeSignal]:
        """
        Per ogni symbol: calcola lo score ensemble pesato e converte in TradeSignal.

        Formula: score_ensemble = Σ(wᵢ · scoreᵢ) / Σwᵢ
        Confidence ensemble: media pesata delle confidence (stesso schema).
        Direction: derivata dallo score_ensemble (long/short/flat).
        """
        result: List[TradeSignal] = []

        for sym, weighted_outs in outputs_per_symbol.items():
            if not weighted_outs:
                continue

            total_weight = sum(w for _, w in weighted_outs)
            if total_weight == 0.0:
                continue

            ensemble_score      = sum(o.score      * w for o, w in weighted_outs) / total_weight
            ensemble_confidence = sum(o.confidence * w for o, w in weighted_outs) / total_weight

            # Filtra segnali deboli sotto la soglia
            if abs(ensemble_score) < self._score_threshold:
                continue

            direction = "buy" if ensemble_score > 0 else "sell"

            # Metadati aggregati: lista contributi segnali
            contributors = [
                {
                    "signal_id":  o.signal_id if hasattr(o, "signal_id") else "unknown",
                    "score":      o.score,
                    "confidence": o.confidence,
                    "weight":     w,
                    "direction":  o.direction,
                    **o.metadata,
                }
                for o, w in weighted_outs
            ]

            result.append(TradeSignal(
                symbol        = sym,
                direction     = direction,
                confidence    = ensemble_confidence,
                strategy_name = "signal_registry_ensemble",
                timeframe     = self._default_timeframe,
                metadata      = {
                    "score":        ensemble_score,
                    "contributors": contributors,
                    "n_signals":    len(weighted_outs),
                },
            ))

        return result

    # ── Serializzazione (QSettings / AppState) ─────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializza lo stato del registry in un dict JSON-compatibile.

        Persiste: signal_id, class FQCN, weight, enabled, params.
        Non persiste: istanze Signal (non serializzabili).
        """
        signals_state = {}
        for sid, signal in self._signals.items():
            signals_state[sid] = {
                "class":   f"{type(signal).__module__}.{type(signal).__qualname__}",
                "weight":  self._weights[sid],
                "enabled": self._enabled[sid],
                "params":  signal.get_params(),
            }
        return {
            "score_threshold":   self._score_threshold,
            "default_timeframe": self._default_timeframe,
            "signals":           signals_state,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        signal_instances: Optional[Dict[str, Signal]] = None,
    ) -> "SignalRegistry":
        """
        Ricostruisce un SignalRegistry da un dict (es. caricato da QSettings).

        Parameters
        ----------
        data             : dict prodotto da to_dict().
        signal_instances : dizionario {signal_id: Signal} pre-istanziato.
                           Se None, i segnali non vengono re-registrati
                           (solo threshold e timeframe vengono ripristinati).
        """
        registry = cls(
            score_threshold   = data.get("score_threshold",   _DEFAULT_SCORE_THRESHOLD),
            default_timeframe = data.get("default_timeframe", "1h"),
        )

        if signal_instances is None:
            return registry

        for sid, state in data.get("signals", {}).items():
            signal = signal_instances.get(sid)
            if signal is None:
                logger.warning(
                    "from_dict: signal_id '%s' not found in signal_instances, skipped.", sid
                )
                continue
            params = state.get("params", {})
            if params:
                try:
                    signal.set_params(**params)
                except Exception as exc:
                    logger.warning("from_dict: set_params error for '%s': %s", sid, exc)

            registry.register(
                signal,
                weight  = state.get("weight",  signal.default_weight),
                enabled = state.get("enabled", signal.default_enabled),
            )

        return registry

    # ── Bus notifications (opzionale — silenzioso se bus non disponibile) ──────

    def _notify_registry_changed(self) -> None:
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.emit_registry_changed()
        except Exception:
            pass

    def _notify_weight_updated(self, name: str, weight: float) -> None:
        try:
            from core.signal_bus import get_bus
            bus = get_bus()
            bus.emit_weight_updated(name, weight)
        except Exception:
            pass
