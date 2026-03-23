"""
Pattern Observer — Coda di osservazione pattern tecnici

Ciclo di vita di un pattern:
  FORMING   → pattern rilevato, in attesa di conferma
  CONFIRMED → prezzo ha rotto il livello di conferma → genera TradeSignal
  FAILED    → prezzo ha violato il livello di invalidazione
  EXPIRED   → TTL superato senza conferma

Solo i pattern CONFIRMED generano TradeSignal.
La coda è thread-safe via asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from config.settings import settings
from indicators.patterns import RawPattern
from strategies.base_strategy import TradeSignal
from utils.logger import get_logger

logger = get_logger.bind(name="core.pattern_observer")

# Costanti stato
FORMING   = "forming"
CONFIRMED = "confirmed"
FAILED    = "failed"
EXPIRED   = "expired"


@dataclass
class PatternObservation:
    id: str
    symbol: str
    raw: RawPattern
    status: str                         # forming | confirmed | failed | expired
    forming_since: datetime
    confirmed_at: Optional[datetime] = None
    failed_at: Optional[datetime]   = None
    bars_since_detection: int       = 0

    @property
    def age_seconds(self) -> float:
        return (datetime.utcnow() - self.forming_since).total_seconds()

    @property
    def is_terminal(self) -> bool:
        return self.status in (CONFIRMED, FAILED, EXPIRED)


class PatternObserver:
    """
    Singleton-friendly observer per la coda di pattern in osservazione.

    Usage:
        observer = PatternObserver()
        # Loop watchlist:
        await observer.ingest(symbol, PatternDetector.detect_all(df))
        await observer.update(symbol, df.iloc[-1])
        confirmed = await observer.get_confirmed(symbol)
        # Loop posizioni:
        forming = await observer.get_forming(symbol)
    """

    def __init__(self):
        # {symbol: [PatternObservation, ...]}
        self._obs: Dict[str, List[PatternObservation]] = {}
        self._lock = asyncio.Lock()
        # Tiene traccia degli ID già restituiti da get_confirmed (una sola volta)
        self._delivered: set[str] = set()

    # ── Public API ─────────────────────────────────────────────────────────

    async def ingest(self, symbol: str, patterns: List[RawPattern]) -> int:
        """
        Inserisce i pattern in osservazione, evitando duplicati (stesso nome + TF).
        Usa le soglie di confidenza calibrate per asset class.
        Ritorna il numero di nuovi pattern inseriti.
        """
        asset_class = settings.asset_type_map.get(symbol, "stock")
        min_conf, _, _ = settings.pattern.for_asset_class(asset_class)

        async with self._lock:
            existing = self._obs.setdefault(symbol, [])
            active_names = {
                (o.raw.name, o.raw.timeframe)
                for o in existing
                if o.status == FORMING
            }
            added = 0
            for raw in patterns:
                key = (raw.name, raw.timeframe)
                if key not in active_names and raw.confidence >= min_conf:
                    existing.append(PatternObservation(
                        id=str(uuid.uuid4()),
                        symbol=symbol,
                        raw=raw,
                        status=FORMING,
                        forming_since=datetime.utcnow(),
                    ))
                    active_names.add(key)
                    added += 1
                    logger.debug(
                        f"[{symbol}/{asset_class}] Pattern in osservazione: {raw.name} "
                        f"({raw.direction}, conf={raw.confidence:.2f}, min={min_conf:.2f})"
                    )

            # Cap: tieni solo i più recenti se superano il limite
            if len(existing) > settings.pattern.max_per_symbol:
                forming = [o for o in existing if o.status == FORMING]
                forming.sort(key=lambda o: o.forming_since, reverse=True)
                terminal = [o for o in existing if o.is_terminal]
                self._obs[symbol] = (forming[:settings.pattern.max_per_symbol] + terminal)[-50:]

            return added

    async def update(self, symbol: str, latest_bar: pd.Series) -> None:
        """
        Aggiorna lo stato di tutti i pattern FORMING per `symbol`
        in base all'ultima barra disponibile.
        """
        if symbol not in self._obs:
            return

        price = float(latest_bar.get("close", latest_bar.get("Close", 0)))
        now   = datetime.utcnow()

        async with self._lock:
            for obs in self._obs[symbol]:
                if obs.status != FORMING:
                    continue

                obs.bars_since_detection += 1
                raw = obs.raw

                # ── Fallimento: livello di invalidazione violato ──────────
                if raw.direction == "bullish" and price < raw.invalidation_price:
                    obs.status   = FAILED
                    obs.failed_at = now
                    logger.debug(f"[{symbol}] {raw.name} FAILED (price={price:.5f} < inv={raw.invalidation_price:.5f})")
                    continue
                if raw.direction == "bearish" and price > raw.invalidation_price:
                    obs.status   = FAILED
                    obs.failed_at = now
                    logger.debug(f"[{symbol}] {raw.name} FAILED (price={price:.5f} > inv={raw.invalidation_price:.5f})")
                    continue

                # ── Scadenza: TTL barre per asset class ──────────────────
                asset_class = settings.asset_type_map.get(symbol, "stock")
                _, _, ttl = settings.pattern.for_asset_class(asset_class)
                if obs.bars_since_detection >= ttl:
                    obs.status = EXPIRED
                    logger.debug(f"[{symbol}] {raw.name} EXPIRED after {obs.bars_since_detection} bars")
                    continue

                # ── Conferma ─────────────────────────────────────────────
                if raw.direction == "neutral":
                    # Doji / Spinning Top: confermati dopo 1 barra (segnale di indecisione)
                    if obs.bars_since_detection >= 1:
                        obs.status       = CONFIRMED
                        obs.confirmed_at = now
                        logger.info(f"[{symbol}] {raw.name} CONFIRMED (neutral)")
                elif raw.direction == "bullish":
                    # Candlestick: basta 1 barra di follow-through
                    # Chart pattern: rottura del livello di conferma
                    needs_bars = 1 if raw.bars_involved <= 3 else 0
                    if obs.bars_since_detection >= needs_bars and price > raw.confirmation_price:
                        obs.status       = CONFIRMED
                        obs.confirmed_at = now
                        logger.info(
                            f"[{symbol}] {raw.name} CONFIRMED BULLISH "
                            f"(price={price:.5f} > conf={raw.confirmation_price:.5f})"
                        )
                elif raw.direction == "bearish":
                    needs_bars = 1 if raw.bars_involved <= 3 else 0
                    if obs.bars_since_detection >= needs_bars and price < raw.confirmation_price:
                        obs.status       = CONFIRMED
                        obs.confirmed_at = now
                        logger.info(
                            f"[{symbol}] {raw.name} CONFIRMED BEARISH "
                            f"(price={price:.5f} < conf={raw.confirmation_price:.5f})"
                        )

    async def get_confirmed(self, symbol: str, consume: bool = True) -> List[PatternObservation]:
        """
        Ritorna i pattern CONFIRMED per il simbolo.
        Con consume=True (default), ogni pattern viene restituito UNA SOLA VOLTA
        (viene marcato come consegnato e non ricomparirà nelle chiamate successive).
        """
        async with self._lock:
            result = []
            for obs in self._obs.get(symbol, []):
                if obs.status == CONFIRMED and obs.id not in self._delivered:
                    result.append(obs)
                    if consume:
                        self._delivered.add(obs.id)
            return result

    async def get_forming(self, symbol: str) -> List[PatternObservation]:
        """Ritorna tutti i pattern FORMING (in osservazione) per il simbolo."""
        async with self._lock:
            return [o for o in self._obs.get(symbol, []) if o.status == FORMING]

    async def get_all(self, symbol: Optional[str] = None) -> List[PatternObservation]:
        """Ritorna tutti i pattern (per un simbolo o per tutti)."""
        async with self._lock:
            if symbol:
                return list(self._obs.get(symbol, []))
            return [o for obs_list in self._obs.values() for o in obs_list]

    async def is_confirmed(self, symbol: str, pattern_name: str) -> bool:
        """Controlla se esiste un pattern confirmed con quel nome (senza consumarlo)."""
        async with self._lock:
            return any(
                o.status == CONFIRMED and o.raw.name == pattern_name
                for o in self._obs.get(symbol, [])
            )

    async def prune(self) -> int:
        """
        Rimuove pattern terminali più vecchi di 24h per tenere la memoria pulita.
        Ritorna il numero di osservazioni rimosse.
        """
        cutoff = datetime.utcnow() - timedelta(hours=24)
        removed = 0
        async with self._lock:
            for symbol in list(self._obs.keys()):
                before = len(self._obs[symbol])
                self._obs[symbol] = [
                    o for o in self._obs[symbol]
                    if not (o.is_terminal and o.forming_since < cutoff)
                ]
                removed += before - len(self._obs[symbol])
                # Pulizia delivered set per pattern rimossi
                ids = {o.id for o in self._obs[symbol]}
                self._delivered = {d for d in self._delivered if d in ids}
        return removed

    async def summary(self) -> Dict:
        """Statistiche aggregate della coda."""
        async with self._lock:
            all_obs = [o for lst in self._obs.values() for o in lst]
            return {
                "total":     len(all_obs),
                "forming":   sum(1 for o in all_obs if o.status == FORMING),
                "confirmed": sum(1 for o in all_obs if o.status == CONFIRMED),
                "failed":    sum(1 for o in all_obs if o.status == FAILED),
                "expired":   sum(1 for o in all_obs if o.status == EXPIRED),
                "symbols":   list(self._obs.keys()),
            }

    # ── TradeSignal conversion ─────────────────────────────────────────────

    @staticmethod
    def to_trade_signal(obs: PatternObservation, current_price: float) -> TradeSignal:
        """
        Converte un PatternObservation CONFIRMED in TradeSignal compatibile
        con il sistema di segnali esistente (risk manager, executor, GUI).
        """
        raw = obs.raw
        direction = "buy" if raw.direction == "bullish" else \
                    "sell" if raw.direction == "bearish" else "close"

        return TradeSignal(
            symbol=obs.symbol,
            direction=direction,
            confidence=raw.confidence,
            strategy_name=f"pattern_{raw.name.lower().replace(' ', '_')}",
            price=current_price,
            stop_loss=raw.invalidation_price,
            take_profit=raw.target_price,
            timeframe=raw.timeframe,
            metadata={
                "pattern_name":       raw.name,
                "pattern_direction":  raw.direction,
                "bars_involved":      raw.bars_involved,
                "bars_to_confirm":    obs.bars_since_detection,
                "confirmed_at":       obs.confirmed_at.isoformat() if obs.confirmed_at else None,
                "forming_since":      obs.forming_since.isoformat(),
                "confirmation_price": raw.confirmation_price,
                **raw.metadata,
            },
        )


# Singleton globale (condiviso tra orchestrator e strategy)
_observer: Optional[PatternObserver] = None


def get_pattern_observer() -> PatternObserver:
    global _observer
    if _observer is None:
        _observer = PatternObserver()
    return _observer
