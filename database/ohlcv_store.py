"""
OHLCV Store — SQLite-backed long-term OHLCV bar storage.

Acts as a persistent cache layer in front of the live data feeds:
  1. On every get_ohlcv request, check DB first.
  2. If data is fresh enough, return from DB (no network call).
  3. After a successful network download, upsert all bars into DB.

This makes TradingIA resilient to network outages: if the download fails,
it returns the last known bars from the database.

TTL policy (how long DB data is considered "fresh"):
  - 1d, 1wk, 1mo : 12 hours  (daily bars rarely change intraday)
  - 4h, 1h       : 1 hour
  - 30m, 15m     : 30 minutes
  - 5m, 1m       : 10 minutes
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database.db import AsyncSessionLocal, init_db
from database.models import OHLCVBar
from utils.logger import get_logger

logger = get_logger.bind(name="database.ohlcv_store")

# Freshness TTL per timeframe
_TTL: Dict[str, timedelta] = {
    "1m":  timedelta(minutes=10),
    "5m":  timedelta(minutes=10),
    "15m": timedelta(minutes=30),
    "30m": timedelta(minutes=30),
    "1h":  timedelta(hours=1),
    "4h":  timedelta(hours=1),
    "1d":  timedelta(hours=12),
    "1wk": timedelta(hours=12),
    "1mo": timedelta(hours=24),
}

_DB_READY = False


async def _ensure_db():
    global _DB_READY
    if not _DB_READY:
        await init_db()
        _DB_READY = True


class OHLCVStore:
    """
    Async interface to persist and retrieve OHLCV bars from SQLite.
    """

    # ── Public API ────────────────────────────────────────────────────────

    async def get(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> Optional[pd.DataFrame]:
        """
        Return cached bars if they are fresh enough, else None.
        """
        try:
            await _ensure_db()
            ttl = _TTL.get(timeframe, timedelta(hours=1))
            cutoff = datetime.utcnow() - ttl

            async with AsyncSessionLocal() as session:
                # Check if we have fresh rows
                freshness_check = await session.execute(
                    select(func.max(OHLCVBar.stored_at))
                    .where(
                        OHLCVBar.symbol == symbol,
                        OHLCVBar.timeframe == timeframe,
                    )
                )
                last_stored = freshness_check.scalar()
                if last_stored is None or last_stored < cutoff:
                    return None   # stale or missing

                # Fetch the last `limit` bars ordered by timestamp
                result = await session.execute(
                    select(OHLCVBar)
                    .where(
                        OHLCVBar.symbol == symbol,
                        OHLCVBar.timeframe == timeframe,
                    )
                    .order_by(OHLCVBar.timestamp.desc())
                    .limit(limit)
                )
                rows = result.scalars().all()
                if not rows:
                    return None

            return self._rows_to_df(rows[::-1])   # chronological order

        except Exception as e:
            logger.debug(f"OHLCVStore.get error ({symbol} {timeframe}): {e}")
            return None

    async def store(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
    ) -> None:
        """
        Upsert all bars from df into the database.
        Uses SQLite INSERT OR REPLACE for idempotent upserts.
        """
        if df is None or df.empty:
            return
        try:
            await _ensure_db()
            now = datetime.utcnow()

            records = []
            for ts, row in df.iterrows():
                ts_dt = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                records.append({
                    "symbol":    symbol,
                    "timeframe": timeframe,
                    "timestamp": ts_dt,
                    "open":      float(row["open"]),
                    "high":      float(row["high"]),
                    "low":       float(row["low"]),
                    "close":     float(row["close"]),
                    "volume":    float(row.get("volume", 0)),
                    "stored_at": now,
                })

            # Batch inserts in chunks: SQLite has a SQLITE_MAX_VARIABLE_NUMBER limit.
            # 500 bars × 9 columns = 4500 variables → exceeds 999 limit on some builds.
            # Chunking at 90 rows keeps us well under (90 × 9 = 810 variables).
            _CHUNK = 90
            async with AsyncSessionLocal() as session:
                for i in range(0, len(records), _CHUNK):
                    chunk = records[i:i + _CHUNK]
                    stmt = sqlite_insert(OHLCVBar).values(chunk)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["symbol", "timeframe", "timestamp"],
                        set_={
                            "open":      stmt.excluded.open,
                            "high":      stmt.excluded.high,
                            "low":       stmt.excluded.low,
                            "close":     stmt.excluded.close,
                            "volume":    stmt.excluded.volume,
                            "stored_at": stmt.excluded.stored_at,
                        },
                    )
                    await session.execute(stmt)
                await session.commit()

            logger.debug(f"OHLCVStore: stored {len(records)} bars for {symbol} {timeframe}")

        except Exception as e:
            logger.warning(f"OHLCVStore.store error ({symbol} {timeframe}): {e}")

    async def get_last_timestamp(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[datetime]:
        """Return timestamp of the most recent stored bar, or None."""
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(func.max(OHLCVBar.timestamp))
                    .where(
                        OHLCVBar.symbol == symbol,
                        OHLCVBar.timeframe == timeframe,
                    )
                )
                return result.scalar()
        except Exception as e:
            logger.debug(f"get_last_timestamp error ({symbol} {timeframe}): {e}")
            return None

    async def get_raw(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 0,
    ) -> Optional[pd.DataFrame]:
        """Return the last `limit` bars without TTL check (always from DB).
        limit=0 means no limit — returns the entire history.
        """
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                q = (
                    select(OHLCVBar)
                    .where(
                        OHLCVBar.symbol == symbol,
                        OHLCVBar.timeframe == timeframe,
                    )
                    .order_by(OHLCVBar.timestamp.desc())
                )
                if limit > 0:
                    q = q.limit(limit)
                result = await session.execute(q)
                rows = result.scalars().all()
                if not rows:
                    return None
            return self._rows_to_df(rows[::-1])
        except Exception as e:
            logger.debug(f"get_raw error ({symbol} {timeframe}): {e}")
            return None

    async def purge_old(self, keep_days: int = 30) -> int:
        """
        Delete bars older than `keep_days` days to prevent DB bloat.
        Returns number of deleted rows.
        """
        try:
            await _ensure_db()
            cutoff = datetime.utcnow() - timedelta(days=keep_days)
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    delete(OHLCVBar).where(OHLCVBar.timestamp < cutoff)
                )
                await session.commit()
                deleted = result.rowcount
            logger.info(f"OHLCVStore: purged {deleted} bars older than {keep_days} days")
            return deleted
        except Exception as e:
            logger.warning(f"OHLCVStore.purge_old error: {e}")
            return 0

    async def get_symbols(self) -> list:
        """Return list of (symbol, timeframe) pairs stored in DB."""
        try:
            await _ensure_db()
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(OHLCVBar.symbol, OHLCVBar.timeframe)
                    .distinct()
                )
                return [{"symbol": r[0], "timeframe": r[1]} for r in result.all()]
        except Exception:
            return []

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _rows_to_df(rows: list) -> pd.DataFrame:
        data = {
            "open":   [r.open   for r in rows],
            "high":   [r.high   for r in rows],
            "low":    [r.low    for r in rows],
            "close":  [r.close  for r in rows],
            "volume": [r.volume for r in rows],
        }
        index = pd.DatetimeIndex([r.timestamp for r in rows], name="timestamp", tz="UTC")
        return pd.DataFrame(data, index=index)


# ── Singleton ─────────────────────────────────────────────────────────────────
ohlcv_store = OHLCVStore()
