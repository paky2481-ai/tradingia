"""
TradingIA - Global Configuration
Supports stocks, forex, crypto, commodities, indices
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Any, List, Dict, Optional
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class DatabaseSettings(BaseSettings):
    url: str = f"sqlite+aiosqlite:///{BASE_DIR}/data/tradingia.db"
    echo: bool = False

    class Config:
        env_prefix = "DB_"


class BrokerSettings(BaseSettings):
    # Alpaca (stocks/crypto)
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # CCXT (crypto exchanges)
    ccxt_exchange: str = "binance"
    ccxt_api_key: str = ""
    ccxt_secret: str = ""
    ccxt_sandbox: bool = True

    # Interactive Brokers
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1

    # IG Markets (forex/indici/commodity CFD)
    ig_api_key: str = ""
    ig_username: str = ""
    ig_password: str = ""
    ig_account_type: str = "demo"   # "demo" o "live"
    ig_account_id: str = ""

    # OANDA (forex, XAU/USD)
    oanda_api_token: str = ""
    oanda_account_id: str = ""
    oanda_environment: str = "practice"   # "practice" o "live"

    # Broker attivo per trading automatico
    # Valori: "paper" | "ig" | "oanda" | "alpaca" | "ccxt"
    active_broker: str = "paper"

    class Config:
        env_prefix = "BROKER_"


class DataSettings(BaseSettings):
    # Yahoo Finance (free, stocks/forex/crypto/commodities)
    yfinance_enabled: bool = True

    # Alpha Vantage — https://www.alphavantage.co/support/#api-key (free, 25 req/day)
    alpha_vantage_key: str = ""

    # Financial Modeling Prep — https://financialmodelingprep.com/developer/docs (free, 250 req/day)
    # La chiave "demo" funziona per dati di base su simboli popolari senza registrazione
    fmp_api_key: str = "demo"

    # Data cache
    cache_dir: str = str(BASE_DIR / "data" / "cache")
    cache_ttl_minutes: int = 5

    class Config:
        env_prefix = "DATA_"


class RiskSettings(BaseSettings):
    max_portfolio_risk_pct: float = 2.0       # max % capital at risk per trade
    max_drawdown_pct: float = 15.0             # stop trading if DD exceeds
    max_open_positions: int = 10
    max_position_size_pct: float = 10.0        # max % portfolio per position
    default_stop_loss_pct: float = 2.0
    default_take_profit_pct: float = 4.0
    kelly_fraction: float = 0.25               # fractional Kelly for sizing
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 1.5

    class Config:
        env_prefix = "RISK_"


class MLSettings(BaseSettings):
    lookback_window: int = 60                  # bars for sequence models
    prediction_horizon: int = 5                # bars ahead to predict
    train_test_split: float = 0.8
    retrain_interval_hours: int = 24
    models_dir: str = str(BASE_DIR / "models" / "saved")
    min_confidence: float = 0.6               # minimum signal confidence

    # Training modes
    # full_train_limit=0 → scarica tutto il disponibile (730d per 1h, max per 1d)
    full_train_limit: int = 0
    # giorni di dati per il retraining incrementale (nightly)
    incremental_train_days: int = 90
    # retraining notturno automatico
    nightly_retrain_enabled: bool = True
    nightly_retrain_hour: int = 2              # ora UTC (default: 02:05)

    class Config:
        env_prefix = "ML_"


class CycleSettings(BaseSettings):
    hurst_min_window: int = 10
    hurst_max_window: int = 100
    fft_max_period: int = 50
    fft_min_period: int = 4
    # Regime thresholds
    trending_hurst: float = 0.55
    cycling_hurst: float = 0.45
    adx_trend_threshold: float = 25.0

    class Config:
        env_prefix = "CYCLE_"


class FundamentalSettings(BaseSettings):
    enabled_asset_types: List[str] = ["stock", "forex", "commodity"]
    cache_ttl_minutes: int = 60
    # Stock scoring
    fair_pe: float = 20.0
    good_pe_low: float = 10.0
    good_pe_high: float = 30.0
    base_dividend_yield: float = 0.03
    good_roe: float = 0.15
    max_debt_equity: float = 2.0
    good_growth: float = 0.10
    # Tassi banche centrali (aggiornati Marzo 2026 — override via env FUND_RATE_XXX)
    rate_usd: float = 4.25   # Fed Funds Rate
    rate_eur: float = 2.50   # ECB Deposit Rate
    rate_gbp: float = 4.50   # BoE Base Rate
    rate_jpy: float = 0.50   # BoJ Policy Rate
    rate_aud: float = 4.10   # RBA Cash Rate
    rate_cad: float = 3.25   # BoC Target Rate
    rate_chf: float = 0.50   # SNB Policy Rate
    rate_nzd: float = 3.75   # RBNZ OCR

    class Config:
        env_prefix = "FUND_"


class AutoConfigSettings(BaseSettings):
    enabled: bool = True
    retune_interval_hours: int = 1
    param_grid_lookback_bars: int = 300
    min_history_for_meta: int = 50
    # Number of top indicators to select per analysis
    top_n_indicators: int = 8

    class Config:
        env_prefix = "AUTOCONF_"


class TimeframeSelectorSettings(BaseSettings):
    """
    Configurazione per la selezione automatica del timeframe ottimale.

    L'AI analizza Hurst exponent, ciclo dominante FFT e autocorrelazione
    dei ritorni per determinare quale timeframe offre il miglior
    rapporto segnale/rumore per ogni strumento.
    """
    enabled: bool = True
    # Periodo ciclo dominante "ideale" in barre (Bollinger 20, SMA 20, RSI 14-21)
    ideal_cycle_bars: int = 20
    # Minimo barre per un'analisi affidabile
    min_bars: int = 50

    class Config:
        env_prefix = "TFSELECTOR_"


class PatternSettings(BaseSettings):
    """
    Configurazione per il modulo di riconoscimento pattern.

    Pattern candlestick (1-3 candele) e chart pattern (10-60 barre).
    Due thread separati: watchlist (apertura) e posizioni aperte (chiusura).

    Le soglie globali sono il fallback. Le soglie per asset class
    (asset_class_overrides) sovrascrivono per i simboli riconosciuti.
    """
    enabled: bool = True
    candlestick_enabled: bool = True
    chart_patterns_enabled: bool = True

    # Soglie globali di fallback (usate se l'asset class è sconosciuta)
    min_confidence: float = 0.60
    min_signal_confidence: float = 0.65

    # Ciclo di vita osservazione
    ttl_bars: int = 10              # barre max prima di expire (senza conferma)
    max_per_symbol: int = 8         # max pattern in osservazione contemporaneamente

    # Intervalli loop (secondi)
    watchlist_scan_interval_s: int = 300    # ogni 5 min — scansione watchlist
    position_scan_interval_s: int = 30     # ogni 30s — controllo posizioni aperte

    # Soglie per asset class — override le soglie globali.
    # Calibrate da Chloe in base alla microstructura di ogni mercato:
    #   stock    — daily/weekly pattern più affidabili, conferma lenta
    #   index    — chart pattern eccellenti, meno rumore degli stock
    #   forex    — mean-reverting, conferma media, pattern su 4h/daily
    #   crypto   — alta volatilità, rumore elevato, soglie più alte e TTL breve
    #   commodity — fundamentals-driven, TA meno affidabile → soglie conservative
    asset_class_overrides: Dict[str, Any] = Field(default_factory=lambda: {
        "stock":     {"min_confidence": 0.62, "min_signal_confidence": 0.65, "ttl_bars": 12},
        "index":     {"min_confidence": 0.60, "min_signal_confidence": 0.63, "ttl_bars": 15},
        "forex":     {"min_confidence": 0.65, "min_signal_confidence": 0.68, "ttl_bars": 8},
        "crypto":    {"min_confidence": 0.72, "min_signal_confidence": 0.75, "ttl_bars": 6},
        "commodity": {"min_confidence": 0.67, "min_signal_confidence": 0.70, "ttl_bars": 10},
    })

    def for_asset_class(self, asset_class: str) -> tuple:
        """
        Ritorna (min_confidence, min_signal_confidence, ttl_bars) per asset class.
        Usa le soglie globali come fallback se l'asset class non è configurata.
        """
        ov = self.asset_class_overrides.get(asset_class, {})
        return (
            ov.get("min_confidence",        self.min_confidence),
            ov.get("min_signal_confidence", self.min_signal_confidence),
            ov.get("ttl_bars",              self.ttl_bars),
        )

    class Config:
        env_prefix = "PATTERN_"


class NotificationSettings(BaseSettings):
    telegram_token: str = ""
    telegram_chat_id: str = ""
    email_smtp: str = ""
    email_from: str = ""
    email_to: str = ""
    email_password: str = ""
    notify_on_trade: bool = True
    notify_on_alert: bool = True

    class Config:
        env_prefix = "NOTIFY_"


class DashboardSettings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    secret_key: str = "tradingia-secret-change-in-prod"

    class Config:
        env_prefix = "DASHBOARD_"


class Settings(BaseSettings):
    # General
    app_name: str = "TradingIA"
    version: str = "1.0.0"
    env: str = "development"
    log_level: str = "INFO"
    log_dir: str = str(BASE_DIR / "logs")
    timezone: str = "UTC"

    # Instruments universe
    stock_symbols: List[str] = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
        "SPY", "QQQ", "IWM"
    ]
    forex_pairs: List[str] = [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X",
        "USDCHF=X", "USDCAD=X", "NZDUSD=X"
    ]
    crypto_symbols: List[str] = [
        "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD",
        "XRP-USD", "ADA-USD", "AVAX-USD"
    ]
    commodity_symbols: List[str] = [
        "GC=F",   # Gold
        "SI=F",   # Silver
        "CL=F",   # Crude Oil
        "NG=F",   # Natural Gas
        "ZC=F",   # Corn
        "ZW=F",   # Wheat
    ]
    index_symbols: List[str] = [
        "^GSPC",  # S&P 500
        "^DJI",   # Dow Jones
        "^IXIC",  # NASDAQ
        "^FTSE",  # FTSE 100
        "^N225",  # Nikkei 225
    ]

    # Timeframes
    timeframes: List[str] = ["1m", "5m", "15m", "1h", "4h", "1d"]
    primary_timeframe: str = "1h"

    # Sub-configs
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    ml: MLSettings = Field(default_factory=MLSettings)
    cycle: CycleSettings = Field(default_factory=CycleSettings)
    fundamental: FundamentalSettings = Field(default_factory=FundamentalSettings)
    autoconfig: AutoConfigSettings = Field(default_factory=AutoConfigSettings)
    tf_selector: TimeframeSelectorSettings = Field(default_factory=TimeframeSelectorSettings)
    pattern: PatternSettings = Field(default_factory=PatternSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"

    @property
    def all_symbols(self) -> List[str]:
        return (
            self.stock_symbols
            + self.forex_pairs
            + self.crypto_symbols
            + self.commodity_symbols
        )

    @property
    def asset_type_map(self) -> Dict[str, str]:
        mapping = {}
        for s in self.stock_symbols:
            mapping[s] = "stock"
        for s in self.forex_pairs:
            mapping[s] = "forex"
        for s in self.crypto_symbols:
            mapping[s] = "crypto"
        for s in self.commodity_symbols:
            mapping[s] = "commodity"
        for s in self.index_symbols:
            mapping[s] = "index"
        return mapping


settings = Settings()

# Ensure directories exist
os.makedirs(settings.log_dir, exist_ok=True)
os.makedirs(settings.data.cache_dir, exist_ok=True)
os.makedirs(settings.ml.models_dir, exist_ok=True)
os.makedirs(BASE_DIR / "data", exist_ok=True)
