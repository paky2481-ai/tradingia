"""
Universal Data Feed
Supports: stocks, forex, crypto, commodities, indices
Sources: yfinance (primary), ccxt (crypto), alpha_vantage (supplementary)
"""

import asyncio
import json
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf
from utils.logger import get_logger
from utils.timeframes import YFINANCE_PERIOD_MAP, resample_ohlcv
from config.settings import settings

logger = get_logger.bind(name="data.feed")


class OHLCVBar:
    """Single OHLCV bar"""
    __slots__ = ("symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume")

    def __init__(self, symbol, timeframe, timestamp, open_, high, low, close, volume):
        self.symbol = symbol
        self.timeframe = timeframe
        self.timestamp = timestamp
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class DataCache:
    """Simple file-based cache for OHLCV data."""

    def __init__(self, cache_dir: str, ttl_minutes: int = 5):
        self.cache_dir = cache_dir
        self.ttl = timedelta(minutes=ttl_minutes)
        os.makedirs(cache_dir, exist_ok=True)

    def _key(self, symbol: str, timeframe: str) -> str:
        safe = symbol.replace("/", "_").replace("=", "_").replace("^", "")
        return os.path.join(self.cache_dir, f"{safe}_{timeframe}.pkl")

    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        path = self._key(symbol, timeframe)
        if not os.path.exists(path):
            return None
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        if datetime.utcnow() - mtime > self.ttl:
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def set(self, symbol: str, timeframe: str, df: pd.DataFrame):
        path = self._key(symbol, timeframe)
        try:
            with open(path, "wb") as f:
                pickle.dump(df, f)
        except Exception as e:
            logger.warning(f"Cache write error: {e}")


class YFinanceFeed:
    """Fetch OHLCV data from Yahoo Finance."""

    def __init__(self):
        self.cache = DataCache(settings.data.cache_dir, settings.data.cache_ttl_minutes)

    async def fetch(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
    ) -> Optional[pd.DataFrame]:
        cached = self.cache.get(symbol, timeframe)
        if cached is not None:
            logger.debug(f"Cache hit: {symbol} {timeframe}")
            return cached.tail(limit)

        period, interval = YFINANCE_PERIOD_MAP.get(timeframe, ("730d", "1d"))

        try:
            df = await asyncio.to_thread(
                self._download, symbol, period, interval
            )
            if df is None or df.empty:
                return None

            # Resample 1h -> 4h if needed
            if timeframe == "4h":
                df = resample_ohlcv(df, "4h")

            self.cache.set(symbol, timeframe, df)
            return df.tail(limit)

        except Exception as e:
            logger.error(f"YFinance error for {symbol}: {e}")
            return None

    def _download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return df

        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        df.dropna(inplace=True)
        return df

    async def fetch_quote(self, symbol: str) -> Optional[Dict]:
        try:
            info = await asyncio.to_thread(self._get_quote, symbol)
            return info
        except Exception as e:
            logger.error(f"Quote error for {symbol}: {e}")
            return None

    def _get_quote(self, symbol: str) -> Dict:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        return {
            "symbol": symbol,
            "price": getattr(info, "last_price", None),
            "open": getattr(info, "open", None),
            "high": getattr(info, "day_high", None),
            "low": getattr(info, "day_low", None),
            "volume": getattr(info, "last_volume", None),
            "market_cap": getattr(info, "market_cap", None),
            "timestamp": datetime.utcnow().isoformat(),
        }


class CCXTFeed:
    """Fetch OHLCV data from crypto exchanges via ccxt."""

    def __init__(self):
        self._exchange = None
        self.cache = DataCache(settings.data.cache_dir, settings.data.cache_ttl_minutes)

    async def _get_exchange(self):
        if self._exchange is None:
            try:
                import ccxt.async_support as ccxt
                exchange_cls = getattr(ccxt, settings.broker.ccxt_exchange)
                self._exchange = exchange_cls({
                    "apiKey": settings.broker.ccxt_api_key or None,
                    "secret": settings.broker.ccxt_secret or None,
                    "sandbox": settings.broker.ccxt_sandbox,
                    "enableRateLimit": True,
                })
            except Exception as e:
                logger.error(f"CCXT init error: {e}")
                return None
        return self._exchange

    async def fetch(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
    ) -> Optional[pd.DataFrame]:
        # Convert yfinance symbol to ccxt format: BTC-USD -> BTC/USDT
        ccxt_symbol = symbol.replace("-USD", "/USDT").replace("-USDT", "/USDT")

        cached = self.cache.get(ccxt_symbol, timeframe)
        if cached is not None:
            return cached.tail(limit)

        exchange = await self._get_exchange()
        if exchange is None:
            return None

        try:
            ohlcv = await exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)
            if not ohlcv:
                return None

            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df.set_index("timestamp", inplace=True)
            self.cache.set(ccxt_symbol, timeframe, df)
            return df
        except Exception as e:
            logger.warning(f"CCXT error {ccxt_symbol}: {e}")
            return None

    async def close(self):
        if self._exchange:
            await self._exchange.close()


class UniversalDataFeed:
    """
    Single interface for all asset types.
    Routes to appropriate underlying feed automatically.

    Data priority:
      1. 5-min pickle cache (fast, in-memory equivalent)
      2. SQLite OHLCV store (long-term, survives restarts)
      3. Live network (yfinance / CCXT)
    """

    def __init__(self):
        self.yf_feed = YFinanceFeed()
        self.ccxt_feed = CCXTFeed()
        self.asset_map = settings.asset_type_map
        self._callbacks: Dict[str, List] = {}
        self._ws_tasks: Dict[str, asyncio.Task] = {}
        # Lazy-loaded to avoid import cycle at module level
        self._ohlcv_store = None

    def get_asset_type(self, symbol: str) -> str:
        return self.asset_map.get(symbol, "stock")

    def _get_ohlcv_store(self):
        if self._ohlcv_store is None:
            try:
                from database.ohlcv_store import ohlcv_store
                self._ohlcv_store = ohlcv_store
            except Exception:
                self._ohlcv_store = False   # disabled
        return self._ohlcv_store if self._ohlcv_store else None

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
    ) -> Optional[pd.DataFrame]:
        asset_type = self.get_asset_type(symbol)
        logger.debug(f"Fetching {symbol} ({asset_type}) [{timeframe}]")

        # ── 1. Try ccxt for crypto with API keys configured ────────────
        if asset_type == "crypto" and settings.broker.ccxt_api_key:
            df = await self.ccxt_feed.fetch(symbol, timeframe, limit)
            if df is not None:
                await self._persist(symbol, timeframe, df)
                return df

        # ── 2. Try yfinance (checks 5-min pickle cache internally) ─────
        df = await self.yf_feed.fetch(symbol, timeframe, limit)
        if df is not None:
            await self._persist(symbol, timeframe, df)
            return df

        # ── 3. Fallback: SQLite long-term store ─────────────────────────
        store = self._get_ohlcv_store()
        if store is not None:
            db_df = await store.get(symbol, timeframe, limit)
            if db_df is not None:
                logger.info(
                    f"Network unavailable — using DB data for {symbol} {timeframe} "
                    f"({len(db_df)} bars)"
                )
                return db_df

        return None

    async def _persist(self, symbol: str, timeframe: str, df: pd.DataFrame) -> None:
        """Background task: store bars in SQLite (fire-and-forget)."""
        store = self._get_ohlcv_store()
        if store is not None:
            asyncio.create_task(store.store(symbol, timeframe, df))

    async def get_multiple_ohlcv(
        self,
        symbols: List[str],
        timeframe: str = "1h",
        limit: int = 500,
    ) -> Dict[str, pd.DataFrame]:
        tasks = {s: self.get_ohlcv(s, timeframe, limit) for s in symbols}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        output = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Error fetching {symbol}: {result}")
            elif result is not None:
                output[symbol] = result
        return output

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        return await self.yf_feed.fetch_quote(symbol)

    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        tasks = [self.get_quote(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        output = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, dict):
                output[symbol] = result
        return output

    def subscribe(self, symbol: str, callback):
        """Subscribe to live price updates (polling-based fallback)."""
        if symbol not in self._callbacks:
            self._callbacks[symbol] = []
        self._callbacks[symbol].append(callback)
        if symbol not in self._ws_tasks:
            task = asyncio.create_task(self._poll_loop(symbol))
            self._ws_tasks[symbol] = task

    async def _poll_loop(self, symbol: str, interval: float = 5.0):
        while True:
            try:
                quote = await self.get_quote(symbol)
                if quote and symbol in self._callbacks:
                    for cb in self._callbacks[symbol]:
                        await cb(symbol, quote)
            except Exception as e:
                logger.error(f"Poll error {symbol}: {e}")
            await asyncio.sleep(interval)

    async def close(self):
        for task in self._ws_tasks.values():
            task.cancel()
        await self.ccxt_feed.close()


# Singleton
data_feed = UniversalDataFeed()
