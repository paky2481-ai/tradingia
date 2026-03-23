"""
Fundamental Analysis Data Feed — Multi-Source con Fallback

Gerarchia fonti per ogni asset class:

  Stock:
    1. yfinance  (gratuito, nessuna chiave)
    2. Alpha Vantage OVERVIEW  (gratuito, 25 req/giorno, richiede chiave)
    3. Financial Modeling Prep  (gratuito, 250 req/giorno, chiave "demo" per simboli noti)

  Forex:
    1. Tassi BC hardcoded (sempre disponibile)
    2. USD-index via UUP ETF (yfinance)  → fallback DX-Y.NYB (DXY Index)

  Commodity:
    1. yfinance (stagionalità z-score su storico 4 anni)
    2. Cache stale (sempre, come ultimo fallback)

  Crypto / Index:
    1. yfinance .info (market_cap, beta)

Configurazione (.env):
  DATA_ALPHA_VANTAGE_KEY=XXX
  DATA_FMP_API_KEY=your_key   (o "demo" per simboli popolari senza registrazione)
  FUND_RATE_USD=4.25          # override manuale tassi BC
  FUND_RATE_EUR=2.50
  ...
"""

import asyncio
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import logging

import numpy as np
import pandas as pd

from config.settings import settings
from utils.logger import get_logger

logger = get_logger.bind(name="data.fundamental")

# yfinance emette warning interni su stderr anche quando la rete è down —
# li abbassiamo a DEBUG per evitare spam nei log di produzione.
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("peewee").setLevel(logging.ERROR)

# ── Central bank rates (%) — aggiornati a Marzo 2026 ─────────────────────────
# Override individuale via env: FUND_RATE_USD, FUND_RATE_EUR, ecc.
_CB_RATES: Dict[str, float] = {
    "USD": settings.fundamental.rate_usd,   # Fed Funds Rate  4.25%
    "EUR": settings.fundamental.rate_eur,   # ECB             2.50%
    "GBP": settings.fundamental.rate_gbp,   # BoE             4.50%
    "JPY": settings.fundamental.rate_jpy,   # BoJ             0.50%
    "AUD": settings.fundamental.rate_aud,   # RBA             4.10%
    "CAD": settings.fundamental.rate_cad,   # BoC             3.25%
    "CHF": settings.fundamental.rate_chf,   # SNB             0.50%
    "NZD": settings.fundamental.rate_nzd,   # RBNZ            3.75%
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

# Alpha Vantage OVERVIEW → FundamentalData field mapping
_AV_FIELD_MAP = {
    "TrailingPE":            "pe_ratio",
    "PriceToBookRatio":      "pb_ratio",
    "PriceToSalesRatioTTM":  "ps_ratio",
    "EPS":                   None,          # non mappato direttamente
    "DividendYield":         "dividend_yield",
    "Beta":                  "beta",
    "ReturnOnEquityTTM":     "roe",
    "MarketCapitalization":  "market_cap",
    "ProfitMargin":          "profit_margin",
}

# FMP profile/key-metrics → FundamentalData field mapping
_FMP_FIELD_MAP = {
    "pe":               "pe_ratio",
    "priceToBook":      "pb_ratio",
    "priceToSalesRatio":"ps_ratio",
    "dividendYield":    "dividend_yield",
    "beta":             "beta",
    "roe":              "roe",
    "mktCap":           "market_cap",
    "netProfitMargin":  "profit_margin",
    "debtToEquity":     "debt_equity",
}


@dataclass
class FundamentalData:
    symbol: str
    asset_type: str
    source: str = "unknown"                   # yfinance | alphavantage | fmp | hardcoded
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    # ── Stock fields ─────────────────────────────────────────────────────
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    eps_growth: Optional[float] = None
    revenue_growth: Optional[float] = None
    debt_equity: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    beta: Optional[float] = None
    profit_margin: Optional[float] = None

    # ── Forex fields ─────────────────────────────────────────────────────
    rate_differential: Optional[float] = None
    usd_index_1m_pct: Optional[float] = None

    # ── Commodity fields ─────────────────────────────────────────────────
    seasonality_score: Optional[float] = None
    year_to_year_pct: Optional[float] = None


class FundamentalFeed:
    """
    Async fundamental data fetcher con 1-ora TTL e fallback multi-source.
    """

    _TTL_SECONDS = 3600   # 1 ora

    def __init__(self):
        self._cache: Dict[str, Tuple[FundamentalData, datetime]] = {}

    # ── Public API ────────────────────────────────────────────────────────

    async def get_fundamentals(
        self, symbol: str, asset_type: str
    ) -> Optional[FundamentalData]:
        """
        Ritorna dati fondamentali (dalla cache se freschi, altrimenti li scarica).
        Tenta le fonti in ordine fino a ottenere dati validi.
        """
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
                data = await self._fetch_generic(symbol, asset_type)

            if data is not None:
                self._cache[cache_key] = (data, now)
            return data

        except Exception as e:
            logger.warning(f"FundamentalFeed error for {symbol}: {e}")
            return cached[0] if cached else None

    # ── Stock: 3 fonti in cascata ──────────────────────────────────────────

    async def _fetch_stock(self, symbol: str) -> Optional[FundamentalData]:
        """Tenta yfinance → Alpha Vantage → FMP in ordine."""

        # Fonte 1: yfinance
        data = await self._fetch_stock_yfinance(symbol)
        if data is not None:
            logger.debug(f"{symbol}: fondamentali da yfinance")
            return data

        # Fonte 2: Alpha Vantage
        if settings.data.alpha_vantage_key:
            data = await self._fetch_stock_alphavantage(symbol)
            if data is not None:
                logger.info(f"{symbol}: fondamentali da Alpha Vantage (yfinance non disponibile)")
                return data

        # Fonte 3: FMP
        if settings.data.fmp_api_key:
            data = await self._fetch_stock_fmp(symbol)
            if data is not None:
                logger.info(f"{symbol}: fondamentali da FMP (yfinance+AV non disponibili)")
                return data

        logger.warning(f"{symbol}: nessuna fonte fondamentale disponibile")
        return None

    async def _fetch_stock_yfinance(self, symbol: str) -> Optional[FundamentalData]:
        def _sync():
            import io, contextlib
            try:
                import yfinance as yf
                with contextlib.redirect_stderr(io.StringIO()), \
                     contextlib.redirect_stdout(io.StringIO()):
                    info = yf.Ticker(symbol).info
                if not info or len(info) < 5:
                    return None

                def _safe(key):
                    v = info.get(key)
                    if v is None or (isinstance(v, float) and np.isnan(v)):
                        return None
                    return float(v) if isinstance(v, (int, float)) else None

                return FundamentalData(
                    symbol=symbol,
                    asset_type="stock",
                    source="yfinance",
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
            except Exception as e:
                logger.debug(f"{symbol} yfinance error: {e}")
                return None

        return await asyncio.to_thread(_sync)

    async def _fetch_stock_alphavantage(self, symbol: str) -> Optional[FundamentalData]:
        """
        Alpha Vantage COMPANY_OVERVIEW endpoint.
        Free tier: 25 req/giorno, 5 req/minuto.
        Chiave gratuita: https://www.alphavantage.co/support/#api-key
        """
        url = (
            "https://www.alphavantage.co/query"
            f"?function=OVERVIEW&symbol={symbol}"
            f"&apikey={settings.data.alpha_vantage_key}"
        )
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    raw = await resp.json(content_type=None)

            if not raw or "Symbol" not in raw:
                return None

            def _safe(key):
                v = raw.get(key, "None")
                if v in ("None", "", "-", None):
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            # Alpha Vantage restituisce growth come stringa annua (es. "0.15")
            eps_g = _safe("QuarterlyEarningsGrowthYOY")
            rev_g = _safe("QuarterlyRevenueGrowthYOY")

            return FundamentalData(
                symbol=symbol,
                asset_type="stock",
                source="alphavantage",
                pe_ratio=_safe("TrailingPE"),
                pb_ratio=_safe("PriceToBookRatio"),
                ps_ratio=_safe("PriceToSalesRatioTTM"),
                eps_growth=eps_g,
                revenue_growth=rev_g,
                debt_equity=None,          # non disponibile in OVERVIEW
                roe=_safe("ReturnOnEquityTTM"),
                dividend_yield=_safe("DividendYield"),
                market_cap=_safe("MarketCapitalization"),
                beta=_safe("Beta"),
                profit_margin=_safe("ProfitMargin"),
            )

        except Exception as e:
            logger.debug(f"{symbol} AlphaVantage error: {e}")
            return None

    async def _fetch_stock_fmp(self, symbol: str) -> Optional[FundamentalData]:
        """
        Financial Modeling Prep — profile + key-metrics endpoint.
        Free tier: 250 req/giorno. Chiave "demo" per simboli popolari (AAPL, MSFT, ecc.).
        Registrazione gratuita: https://financialmodelingprep.com/developer/docs
        """
        base = "https://financialmodelingprep.com/api/v3"
        key  = settings.data.fmp_api_key

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                # Endpoint 1: profile (PE, PB, beta, market cap)
                async with session.get(
                    f"{base}/profile/{symbol}?apikey={key}"
                ) as resp:
                    profile_raw = await resp.json(content_type=None) if resp.status == 200 else []

                # Endpoint 2: key-metrics (ROE, D/E, PS, profit margin)
                async with session.get(
                    f"{base}/key-metrics-ttm/{symbol}?apikey={key}"
                ) as resp:
                    metrics_raw = await resp.json(content_type=None) if resp.status == 200 else []

            profile  = profile_raw[0]  if isinstance(profile_raw, list)  and profile_raw  else {}
            metrics  = metrics_raw[0]  if isinstance(metrics_raw, list)   and metrics_raw  else {}

            if not profile and not metrics:
                return None

            def _safe(d, key):
                v = d.get(key)
                if v is None:
                    return None
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return None

            # Cerca eps/revenue growth nei financial-growth endpoint se non disponibili
            eps_g = _safe(metrics, "epsgrowth") or _safe(metrics, "revenueGrowth")

            return FundamentalData(
                symbol=symbol,
                asset_type="stock",
                source="fmp",
                pe_ratio=_safe(profile, "pe") or _safe(metrics, "peRatioTTM"),
                pb_ratio=_safe(profile, "priceToBook") or _safe(metrics, "pbRatioTTM"),
                ps_ratio=_safe(metrics, "priceToSalesRatioTTM"),
                eps_growth=eps_g,
                revenue_growth=_safe(metrics, "revenueGrowth"),
                debt_equity=_safe(metrics, "debtToEquityTTM"),
                roe=_safe(metrics, "roeTTM"),
                dividend_yield=_safe(profile, "lastDiv"),
                market_cap=_safe(profile, "mktCap"),
                beta=_safe(profile, "beta"),
                profit_margin=_safe(metrics, "netProfitMarginTTM"),
            )

        except Exception as e:
            logger.debug(f"{symbol} FMP error: {e}")
            return None

    # ── Forex ──────────────────────────────────────────────────────────────

    async def _fetch_forex(self, symbol: str) -> Optional[FundamentalData]:
        currencies = _FOREX_CURRENCIES.get(symbol, ("USD", "USD"))
        base_cur, quote_cur = currencies

        rate_diff = _CB_RATES.get(base_cur, 0.0) - _CB_RATES.get(quote_cur, 0.0)
        usd_1m    = await self._fetch_usd_index_1m()

        return FundamentalData(
            symbol=symbol,
            asset_type="forex",
            source="hardcoded+usd_index",
            rate_differential=rate_diff,
            usd_index_1m_pct=usd_1m,
        )

    async def _fetch_usd_index_1m(self) -> Optional[float]:
        """
        Ritorna il rendimento 1-mese dell'indice USD.
        Fonte 1: UUP ETF (USD Bull ETF su yfinance)
        Fonte 2: DX-Y.NYB (DXY spot index su yfinance)
        Fonte 3: None (fallback silenzioso, il forex score usa solo rate_differential)
        """
        for ticker_sym in ("UUP", "DX-Y.NYB"):
            result = await self._fetch_ticker_1m_return(ticker_sym)
            if result is not None:
                logger.debug(f"USD index 1m from {ticker_sym}: {result:.4f}%")
                return result
        logger.debug("USD index non disponibile, forex score usa solo rate differential")
        return None

    async def _fetch_ticker_1m_return(self, ticker_sym: str) -> Optional[float]:
        """Calcola il rendimento % a 1 mese di un ticker yfinance."""
        def _sync():
            import io, contextlib
            try:
                import yfinance as yf
                # yfinance stampa errori di rete via print() — sopprimi stderr/stdout
                with contextlib.redirect_stderr(io.StringIO()), \
                     contextlib.redirect_stdout(io.StringIO()):
                    hist = yf.Ticker(ticker_sym).history(period="2mo", interval="1d")
                if hist is None or len(hist) < 20:
                    return None
                hist.columns = [c.lower() for c in hist.columns]
                prices = hist["close"].dropna()
                if len(prices) < 20:
                    return None
                pct = (prices.iloc[-1] / prices.iloc[-21] - 1.0) * 100
                return round(float(pct), 4)
            except Exception as e:
                logger.debug(f"{ticker_sym} 1m return error: {e}")
                return None

        return await asyncio.to_thread(_sync)

    # ── Commodity ─────────────────────────────────────────────────────────

    async def _fetch_commodity(self, symbol: str) -> Optional[FundamentalData]:
        """Stagionalità z-score via yfinance. Unica fonte disponibile gratuitamente."""
        def _sync():
            import io, contextlib
            try:
                import yfinance as yf
                with contextlib.redirect_stderr(io.StringIO()), \
                     contextlib.redirect_stdout(io.StringIO()):
                    hist = yf.Ticker(symbol).history(period="4y", interval="1mo")
                if hist is None or len(hist) < 12:
                    return None
                hist.columns = [c.lower() for c in hist.columns]
                if "close" not in hist.columns:
                    return None

                prices = hist["close"].dropna()
                now = datetime.utcnow()
                current_month = now.month
                current_price = float(prices.iloc[-1])

                monthly_prices = []
                for year_offset in range(1, 4):
                    target_year = now.year - year_offset
                    for date, price in prices.items():
                        if hasattr(date, "month") and date.month == current_month \
                                and date.year == target_year:
                            monthly_prices.append(float(price))
                            break

                if len(monthly_prices) >= 2:
                    mu = np.mean(monthly_prices)
                    sigma = np.std(monthly_prices) if len(monthly_prices) > 1 else 1.0
                    z = (current_price - mu) / (sigma + 1e-10)
                    seasonality = round(float(np.clip(z / 2.0, -1.0, 1.0)), 4)
                else:
                    seasonality = None

                yoy_pct = None
                if len(prices) >= 13:
                    yoy_pct = round(float((prices.iloc[-1] / prices.iloc[-13] - 1.0) * 100), 4)

                return FundamentalData(
                    symbol=symbol,
                    asset_type="commodity",
                    source="yfinance",
                    seasonality_score=seasonality,
                    year_to_year_pct=yoy_pct,
                )
            except Exception as e:
                logger.debug(f"{symbol} commodity error: {e}")
                return None

        return await asyncio.to_thread(_sync)

    # ── Generic (crypto / index) ──────────────────────────────────────────

    async def _fetch_generic(self, symbol: str, asset_type: str) -> Optional[FundamentalData]:
        def _sync():
            import io, contextlib
            try:
                import yfinance as yf
                with contextlib.redirect_stderr(io.StringIO()), \
                     contextlib.redirect_stdout(io.StringIO()):
                    info = yf.Ticker(symbol).info
                if not info:
                    return None
                return FundamentalData(
                    symbol=symbol,
                    asset_type=asset_type,
                    source="yfinance",
                    market_cap=info.get("marketCap"),
                    beta=info.get("beta"),
                )
            except Exception as e:
                logger.debug(f"{symbol} generic error: {e}")
                return None

        return await asyncio.to_thread(_sync)


class FundamentalScore:
    """
    Calcola un singolo score scalare da FundamentalData.
    Score: -1.0 (molto ribassista) → +1.0 (molto rialzista).
    """

    FAIR_PE       = 20.0
    GOOD_PE_LOW   = 10.0
    GOOD_PE_HIGH  = 30.0
    BASE_DIVIDEND = 0.03
    GOOD_ROE      = 0.15
    MAX_DEBT_EQUITY = 2.0
    GOOD_GROWTH   = 0.10

    @classmethod
    def compute(cls, data: Optional[FundamentalData], asset_type: str) -> float:
        """Ritorna score in [-1.0, +1.0]. Ritorna 0.0 se data è None."""
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
        components, weights = [], []

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

        if d.pb_ratio is not None and d.pb_ratio > 0:
            pb_score = np.clip(1.0 - (d.pb_ratio - 1.0) / 4.0, -1.0, 1.0)
            components.append(float(pb_score))
            weights.append(0.10)

        if d.eps_growth is not None:
            components.append(float(np.clip(d.eps_growth / cls.GOOD_GROWTH, -1.0, 1.0)))
            weights.append(0.20)

        if d.revenue_growth is not None:
            components.append(float(np.clip(d.revenue_growth / cls.GOOD_GROWTH, -1.0, 1.0)))
            weights.append(0.15)

        if d.roe is not None:
            components.append(float(np.clip(d.roe / cls.GOOD_ROE - 1.0, -1.0, 1.0)))
            weights.append(0.15)

        if d.debt_equity is not None:
            de = d.debt_equity / 100.0   # yfinance restituisce come %, normalizza
            de_score = np.clip(1.0 - de / cls.MAX_DEBT_EQUITY, -1.0, 1.0)
            components.append(float(de_score))
            weights.append(0.10)

        if d.dividend_yield is not None:
            dy_score = np.clip(d.dividend_yield / cls.BASE_DIVIDEND - 1.0, -1.0, 1.0)
            components.append(float(dy_score))
            weights.append(0.05)

        if not components:
            return 0.0

        w = np.array(weights)
        w /= w.sum()
        return round(float(np.clip(np.dot(components, w), -1.0, 1.0)), 4)

    @classmethod
    def _score_forex(cls, d: FundamentalData) -> float:
        components = []

        if d.rate_differential is not None:
            rd_score = np.clip(d.rate_differential / 3.0, -1.0, 1.0)
            components.append(float(rd_score))

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
            yoy_score = np.clip(d.year_to_year_pct / 30.0, -1.0, 1.0)
            components.append(float(yoy_score))

        if not components:
            return 0.0
        return round(float(np.clip(np.mean(components), -1.0, 1.0)), 4)


# ── Singleton ─────────────────────────────────────────────────────────────────
fundamental_feed = FundamentalFeed()
