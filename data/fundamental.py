"""
Fundamental Analysis Data Feed

Supports:
  - Stocks  : P/E, P/B, EPS growth, revenue growth, debt/equity, ROE, dividend yield
  - Forex   : USD-index proxy (UUP ETF) + hardcoded central-bank rate table
  - Commodity: seasonal z-score vs 3-year historical average for the current month
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd


# ── Central bank rates (%) – update via FundamentalSettings env vars ─────────
_CB_RATES: Dict[str, float] = {
    "USD": 5.50,   # Fed Funds Rate
    "EUR": 4.25,   # ECB
    "GBP": 5.25,   # BoE
    "JPY": 0.10,   # BoJ
    "AUD": 4.35,   # RBA
    "CAD": 5.00,   # BoC
    "CHF": 1.75,   # SNB
    "NZD": 5.50,   # RBNZ
}

# Forex symbol → (base_currency, quote_currency)
_FOREX_CURRENCIES: Dict[str, Tuple[str, str]] = {
    "EURUSD=X": ("EUR", "USD"),
    "GBPUSD=X": ("GBP", "USD"),
    "USDJPY=X": ("USD", "JPY"),
    "AUDUSD=X": ("AUD", "USD"),
    "USDCHF=X": ("USD", "CHF"),
    "USDCAD=X": ("USD", "CAD"),
    "NZDUSD=X": ("NZD", "USD"),
}


@dataclass
class FundamentalData:
    symbol: str
    asset_type: str
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    # ── Stock fields ─────────────────────────────────────────────────────
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    eps_growth: Optional[float] = None       # earningsGrowth (yoy)
    revenue_growth: Optional[float] = None   # revenueGrowth  (yoy)
    debt_equity: Optional[float] = None
    roe: Optional[float] = None              # returnOnEquity
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    beta: Optional[float] = None
    profit_margin: Optional[float] = None

    # ── Forex fields ─────────────────────────────────────────────────────
    rate_differential: Optional[float] = None   # base – quote rate (%)
    usd_index_1m_pct: Optional[float] = None    # UUP 1-month price change

    # ── Commodity fields ─────────────────────────────────────────────────
    seasonality_score: Optional[float] = None   # z-score vs 3-yr seasonal avg
    year_to_year_pct: Optional[float] = None    # current price vs same month last year


class FundamentalFeed:
    """
    Async fundamental data fetcher with 1-hour TTL cache.
    """

    _TTL_SECONDS = 3600  # 1 hour

    def __init__(self):
        self._cache: Dict[str, Tuple[FundamentalData, datetime]] = {}

    # ── Public API ────────────────────────────────────────────────────────

    async def get_fundamentals(
        self, symbol: str, asset_type: str
    ) -> Optional[FundamentalData]:
        """Fetch (or return cached) fundamental data for a symbol."""
        cache_key = f"{symbol}_{asset_type}"
        now = datetime.utcnow()

        cached = self._cache.get(cache_key)
        if cached is not None:
            data, ts = cached
            if (now - ts).total_seconds() < self._TTL_SECONDS:
                return data

        try:
            if asset_type == "stock":
                data = await self._fetch_stock(symbol)
            elif asset_type == "forex":
                data = await self._fetch_forex(symbol)
            elif asset_type == "commodity":
                data = await self._fetch_commodity(symbol)
            else:
                # For crypto / index: basic market data from yfinance info
                data = await self._fetch_generic(symbol, asset_type)

            if data is not None:
                self._cache[cache_key] = (data, now)
            return data
        except Exception:
            # Return cached stale data if available, otherwise None
            return cached[0] if cached else None

    # ── Private fetchers ──────────────────────────────────────────────────

    async def _fetch_stock(self, symbol: str) -> Optional[FundamentalData]:
        def _sync() -> Optional[FundamentalData]:
            try:
                import yfinance as yf
                info = yf.Ticker(symbol).info
                if not info:
                    return None

                def _safe(key, default=None):
                    v = info.get(key, default)
                    if v is None or (isinstance(v, float) and np.isnan(v)):
                        return None
                    return float(v) if isinstance(v, (int, float)) else v

                return FundamentalData(
                    symbol=symbol,
                    asset_type="stock",
                    pe_ratio=_safe("trailingPE"),
                    pb_ratio=_safe("priceToBook"),
                    ps_ratio=_safe("priceToSalesTrailing12Months"),
                    eps_growth=_safe("earningsGrowth"),
                    revenue_growth=_safe("revenueGrowth"),
                    debt_equity=_safe("debtToEquity"),
                    roe=_safe("returnOnEquity"),
                    dividend_yield=_safe("dividendYield"),
                    market_cap=_safe("marketCap"),
                    beta=_safe("beta"),
                    profit_margin=_safe("profitMargins"),
                )
            except Exception:
                return None

        return await asyncio.to_thread(_sync)

    async def _fetch_forex(self, symbol: str) -> Optional[FundamentalData]:
        currencies = _FOREX_CURRENCIES.get(symbol, ("USD", "USD"))
        base_cur, quote_cur = currencies

        # Rate differential
        base_rate = _CB_RATES.get(base_cur, 0.0)
        quote_rate = _CB_RATES.get(quote_cur, 0.0)
        rate_diff = base_rate - quote_rate

        # USD-index proxy via UUP ETF 1-month return
        usd_1m = await self._fetch_uup_return()

        return FundamentalData(
            symbol=symbol,
            asset_type="forex",
            rate_differential=rate_diff,
            usd_index_1m_pct=usd_1m,
        )

    async def _fetch_uup_return(self) -> Optional[float]:
        """Compute 1-month return for UUP (USD Bull ETF) as USD-index proxy."""
        def _sync():
            try:
                import yfinance as yf
                uup = yf.Ticker("UUP").history(period="2mo", interval="1d")
                if uup is None or len(uup) < 20:
                    return None
                uup.columns = [c.lower() for c in uup.columns]
                if "close" not in uup.columns:
                    return None
                prices = uup["close"].dropna()
                if len(prices) < 20:
                    return None
                pct = (prices.iloc[-1] / prices.iloc[-21] - 1.0) * 100
                return round(float(pct), 4)
            except Exception:
                return None

        return await asyncio.to_thread(_sync)

    async def _fetch_commodity(self, symbol: str) -> Optional[FundamentalData]:
        """Seasonal z-score: compare current price vs 3-year monthly average."""
        def _sync():
            try:
                import yfinance as yf
                hist = yf.Ticker(symbol).history(period="4y", interval="1mo")
                if hist is None or len(hist) < 12:
                    return None
                hist.columns = [c.lower() for c in hist.columns]
                if "close" not in hist.columns:
                    return None

                hist = hist["close"].dropna()
                now = datetime.utcnow()
                current_month = now.month
                current_price = float(hist.iloc[-1])

                # Get prices for the same calendar month across 3 prior years
                monthly_prices = []
                for year_offset in range(1, 4):
                    target_date = now.replace(year=now.year - year_offset)
                    # Find closest monthly bar
                    for date, price in hist.items():
                        if hasattr(date, "month") and date.month == current_month and \
                           date.year == target_date.year:
                            monthly_prices.append(float(price))
                            break

                if len(monthly_prices) >= 2:
                    mu = np.mean(monthly_prices)
                    sigma = np.std(monthly_prices) if len(monthly_prices) > 1 else 1.0
                    z = (current_price - mu) / (sigma + 1e-10)
                    seasonality = round(float(np.clip(z / 2.0, -1.0, 1.0)), 4)
                else:
                    seasonality = None

                # YoY %
                if len(hist) >= 13:
                    yoy = (hist.iloc[-1] / hist.iloc[-13] - 1.0) * 100
                    yoy_pct = round(float(yoy), 4)
                else:
                    yoy_pct = None

                return FundamentalData(
                    symbol=symbol,
                    asset_type="commodity",
                    seasonality_score=seasonality,
                    year_to_year_pct=yoy_pct,
                )
            except Exception:
                return None

        return await asyncio.to_thread(_sync)

    async def _fetch_generic(self, symbol: str, asset_type: str) -> Optional[FundamentalData]:
        def _sync():
            try:
                import yfinance as yf
                info = yf.Ticker(symbol).info
                return FundamentalData(
                    symbol=symbol,
                    asset_type=asset_type,
                    market_cap=info.get("marketCap"),
                    beta=info.get("beta"),
                )
            except Exception:
                return None

        return await asyncio.to_thread(_sync)


class FundamentalScore:
    """
    Compute a single scalar score from FundamentalData.
    Score: -1.0 (very bearish) to +1.0 (very bullish).
    """

    # Thresholds for stock scoring
    FAIR_PE = 20.0          # "fair" P/E ratio
    GOOD_PE_LOW = 10.0      # cheap territory
    GOOD_PE_HIGH = 30.0     # expensive territory
    BASE_DIVIDEND = 0.03    # 3% as neutral dividend baseline
    GOOD_ROE = 0.15         # 15% ROE = good
    MAX_DEBT_EQUITY = 2.0   # above this = risky
    GOOD_GROWTH = 0.10      # 10% growth = good

    @classmethod
    def compute(cls, data: Optional[FundamentalData], asset_type: str) -> float:
        """Return score in [-1.0, +1.0]. Returns 0.0 if data is None."""
        if data is None:
            return 0.0

        if asset_type == "stock":
            return cls._score_stock(data)
        elif asset_type == "forex":
            return cls._score_forex(data)
        elif asset_type == "commodity":
            return cls._score_commodity(data)
        return 0.0

    @classmethod
    def _score_stock(cls, d: FundamentalData) -> float:
        components = []
        weights = []

        # ── P/E valuation (weight 0.25) ──────────────────────────────────
        if d.pe_ratio is not None and d.pe_ratio > 0:
            pe = d.pe_ratio
            if pe < cls.GOOD_PE_LOW:
                pe_score = 1.0
            elif pe > cls.GOOD_PE_HIGH:
                pe_score = -1.0
            else:
                pe_score = 1.0 - 2.0 * (pe - cls.GOOD_PE_LOW) / (cls.GOOD_PE_HIGH - cls.GOOD_PE_LOW)
            components.append(float(np.clip(pe_score, -1.0, 1.0)))
            weights.append(0.25)

        # ── P/B valuation (weight 0.10) ──────────────────────────────────
        if d.pb_ratio is not None and d.pb_ratio > 0:
            pb_score = np.clip(1.0 - (d.pb_ratio - 1.0) / 4.0, -1.0, 1.0)
            components.append(float(pb_score))
            weights.append(0.10)

        # ── EPS growth (weight 0.20) ─────────────────────────────────────
        if d.eps_growth is not None:
            g = d.eps_growth
            eps_score = np.clip(g / cls.GOOD_GROWTH, -1.0, 1.0)
            components.append(float(eps_score))
            weights.append(0.20)

        # ── Revenue growth (weight 0.15) ─────────────────────────────────
        if d.revenue_growth is not None:
            g = d.revenue_growth
            rev_score = np.clip(g / cls.GOOD_GROWTH, -1.0, 1.0)
            components.append(float(rev_score))
            weights.append(0.15)

        # ── ROE quality (weight 0.15) ────────────────────────────────────
        if d.roe is not None:
            roe_score = np.clip(d.roe / cls.GOOD_ROE - 1.0, -1.0, 1.0)
            components.append(float(roe_score))
            weights.append(0.15)

        # ── Debt/equity safety (weight 0.10) ─────────────────────────────
        if d.debt_equity is not None:
            de = d.debt_equity / 100.0  # yfinance returns as %, normalise
            de_score = np.clip(1.0 - de / cls.MAX_DEBT_EQUITY, -1.0, 1.0)
            components.append(float(de_score))
            weights.append(0.10)

        # ── Dividend yield (weight 0.05) ─────────────────────────────────
        if d.dividend_yield is not None:
            dy_score = np.clip(d.dividend_yield / cls.BASE_DIVIDEND - 1.0, -1.0, 1.0)
            components.append(float(dy_score))
            weights.append(0.05)

        if not components:
            return 0.0

        weights_arr = np.array(weights)
        weights_arr /= weights_arr.sum()
        score = float(np.dot(components, weights_arr))
        return round(np.clip(score, -1.0, 1.0), 4)

    @classmethod
    def _score_forex(cls, d: FundamentalData) -> float:
        components = []

        # Rate differential: positive = base currency has higher rate → bullish
        if d.rate_differential is not None:
            rd_score = np.clip(d.rate_differential / 3.0, -1.0, 1.0)
            components.append(float(rd_score))

        # USD index 1-month momentum (only relevant for USD pairs)
        if d.usd_index_1m_pct is not None:
            usd_score = np.clip(d.usd_index_1m_pct / 3.0, -1.0, 1.0)
            components.append(float(usd_score))

        if not components:
            return 0.0
        return round(float(np.clip(np.mean(components), -1.0, 1.0)), 4)

    @classmethod
    def _score_commodity(cls, d: FundamentalData) -> float:
        components = []

        if d.seasonality_score is not None:
            components.append(float(np.clip(d.seasonality_score, -1.0, 1.0)))

        if d.year_to_year_pct is not None:
            # Normalise YoY % to -1..+1 using ±30% as reference range
            yoy_score = np.clip(d.year_to_year_pct / 30.0, -1.0, 1.0)
            components.append(float(yoy_score))

        if not components:
            return 0.0
        return round(float(np.clip(np.mean(components), -1.0, 1.0)), 4)


# ── Singleton ─────────────────────────────────────────────────────────────────
fundamental_feed = FundamentalFeed()
