"""
TradingIA - Global Configuration
Supports stocks, forex, crypto, commodities, indices
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Dict, Optional
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

    # Alpha Vantage (requires free API key)
    alpha_vantage_key: str = ""

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
    # Central bank rates (overridable via env)
    rate_usd: float = 5.50
    rate_eur: float = 4.25
    rate_gbp: float = 5.25
    rate_jpy: float = 0.10
    rate_aud: float = 4.35
    rate_cad: float = 5.00
    rate_chf: float = 1.75
    rate_nzd: float = 5.50

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
