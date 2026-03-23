"""
AI Config Store — SQLite-backed persistence for AI state.

Persists:
  - AutoConfigResult (regime, strategy, indicators, params, scores) per symbol
  - IndicatorSelector learned weights (all asset_type × regime combos)
  - MetaLearner training history (last N samples)

This allows the AI to pick up exactly where it left off after a restart,
without needing to re-run the full hourly retune pipeline.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import select, delete

from database.db import AsyncSessionLocal, init_db
from database.models import AIConfig
from utils.logger import get_logger

logger = get_logger.bind(name="database.ai_store")

_DB_READY = False


async def _ensure_db():
    global _DB_READY
    if not _DB_READY:
        await init_db()
        _DB_READY = True


class AIConfigStore:
    """
    Async interface to save and restore AI configuration state.
    """

    # ── AutoConfigResult ──────────────────────────────────────────────────

    async def save_config(self, result) -> None:
        """
        Persist an AutoConfigResult to the database.
        `result` is an AutoConfigResult dataclass instance.
        """
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                row = AIConfig(
                    symbol=result.symbol,
                    asset_type=result.asset_type,
                    timestamp=result.timestamp,
                    regime=result.regime,
                    hurst=result.hurst,
                    dominant_period=result.dominant_period,
                    recommended_strategy=result.recommended_strategy,
                    active_indicators=json.dumps(result.active_indicators),
                    indicator_weights=json.dumps(
                        {k: float(v) for k, v in result.indicator_weights.items()}
                    ),
                    tuned_params=json.dumps(result.tuned_params),
                    fundamental_score=result.fundamental_score,
                    oscillator_for_chart=result.oscillator_for_chart,
                    confidence=result.confidence,
                )
                session.add(row)
                await session.commit()
            logger.debug(f"AIConfigStore: saved config for {result.symbol}")
        except Exception as e:
            logger.warning(f"AIConfigStore.save_config error ({result.symbol}): {e}")

    async def load_latest_config(self, symbol: str):
        """
        Load the most recent AutoConfigResult for a symbol.
        Returns a dict (not the dataclass) for decoupling.
        """
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AIConfig)
                    .where(AIConfig.symbol == symbol)
                    .order_by(AIConfig.timestamp.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return None

                return {
                    "symbol":               row.symbol,
                    "asset_type":           row.asset_type,
                    "timestamp":            row.timestamp,
                    "regime":               row.regime,
                    "hurst":                row.hurst,
                    "dominant_period":      row.dominant_period,
                    "recommended_strategy": row.recommended_strategy,
                    "active_indicators":    json.loads(row.active_indicators or "[]"),
                    "indicator_weights":    json.loads(row.indicator_weights or "{}"),
                    "tuned_params":         json.loads(row.tuned_params or "{}"),
                    "fundamental_score":    row.fundamental_score,
                    "oscillator_for_chart": row.oscillator_for_chart,
                    "confidence":           row.confidence,
                }
        except Exception as e:
            logger.debug(f"AIConfigStore.load_latest_config error ({symbol}): {e}")
            return None

    # ── Indicator Selector Weights ────────────────────────────────────────

    async def save_selector_weights(
        self, symbol: str, weights: Dict[str, Dict[str, Dict[str, float]]]
    ) -> None:
        """
        Save IndicatorSelector._weights dict as JSON on the latest AIConfig row
        for this symbol.
        """
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AIConfig)
                    .where(AIConfig.symbol == symbol)
                    .order_by(AIConfig.timestamp.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    row.selector_weights = json.dumps(weights)
                    await session.commit()
                    logger.debug(f"AIConfigStore: saved selector weights for {symbol}")
        except Exception as e:
            logger.debug(f"AIConfigStore.save_selector_weights error ({symbol}): {e}")

    async def load_selector_weights(self, symbol: str) -> Optional[Dict]:
        """Load indicator selector weights from the latest AIConfig row."""
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AIConfig.selector_weights)
                    .where(AIConfig.symbol == symbol)
                    .order_by(AIConfig.timestamp.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row:
                    return json.loads(row)
        except Exception as e:
            logger.debug(f"AIConfigStore.load_selector_weights error ({symbol}): {e}")
        return None

    # ── MetaLearner History ───────────────────────────────────────────────

    async def save_meta_history(
        self,
        symbol: str,
        history: List[Tuple[np.ndarray, int]],
    ) -> None:
        """
        Persist MetaLearner._history for a symbol.
        Serialise feature vectors as JSON lists.
        """
        try:
            await _ensure_db()
            serialised = [
                {"fv": fv.tolist(), "label": int(label)}
                for fv, label in history
            ]
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AIConfig)
                    .where(AIConfig.symbol == symbol)
                    .order_by(AIConfig.timestamp.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    row.meta_learner_history = json.dumps(serialised)
                    await session.commit()
                    logger.debug(
                        f"AIConfigStore: saved {len(serialised)} meta-learner samples for {symbol}"
                    )
        except Exception as e:
            logger.debug(f"AIConfigStore.save_meta_history error ({symbol}): {e}")

    async def load_meta_history(
        self, symbol: str
    ) -> List[Tuple[np.ndarray, int]]:
        """Load MetaLearner history for a symbol."""
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(AIConfig.meta_learner_history)
                    .where(AIConfig.symbol == symbol)
                    .order_by(AIConfig.timestamp.desc())
                    .limit(1)
                )
                raw = result.scalar_one_or_none()
                if raw:
                    data = json.loads(raw)
                    return [
                        (np.array(item["fv"], dtype=np.float32), item["label"])
                        for item in data
                    ]
        except Exception as e:
            logger.debug(f"AIConfigStore.load_meta_history error ({symbol}): {e}")
        return []

    # ── Signals ───────────────────────────────────────────────────────────

    async def save_signal(
        self,
        symbol: str,
        asset_type: str,
        timeframe: str,
        direction: str,
        confidence: float,
        strategy: str,
        price: Optional[float] = None,
        indicators: Optional[dict] = None,
    ) -> None:
        """Persist a TradeSignal to the signals table."""
        try:
            await _ensure_db()
            from database.models import Signal
            async with AsyncSessionLocal() as session:
                row = Signal(
                    symbol=symbol,
                    asset_type=asset_type,
                    timeframe=timeframe,
                    direction=direction,
                    confidence=confidence,
                    strategy=strategy,
                    price=price,
                    indicators=json.dumps(indicators) if indicators else None,
                )
                session.add(row)
                await session.commit()
        except Exception as e:
            logger.debug(f"AIConfigStore.save_signal error ({symbol}): {e}")

    # ── Cleanup ───────────────────────────────────────────────────────────

    async def purge_old_configs(self, keep_days: int = 7) -> int:
        """Keep only configs from the last N days."""
        try:
            from datetime import timedelta
            await _ensure_db()
            cutoff = datetime.utcnow() - timedelta(days=keep_days)
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    delete(AIConfig).where(AIConfig.timestamp < cutoff)
                )
                await session.commit()
                return result.rowcount
        except Exception:
            return 0


# ── Singleton ─────────────────────────────────────────────────────────────────
ai_store = AIConfigStore()
