"""SQLAlchemy database models"""

from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime,
    Enum, Text, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class AssetType(str, enum.Enum):
    STOCK = "stock"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    asset_type = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False, default="market")
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    strategy = Column(String(100), nullable=True)
    signal_confidence = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    commission = Column(Float, nullable=True, default=0.0)
    broker_order_id = Column(String(100), nullable=True)
    timeframe = Column(String(10), nullable=True)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_trades_symbol_status", "symbol", "status"),
        Index("ix_trades_created_at", "created_at"),
    )


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, unique=True, index=True)
    asset_type = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    unrealized_pnl = Column(Float, nullable=True, default=0.0)
    unrealized_pnl_pct = Column(Float, nullable=True, default=0.0)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    trailing_stop = Column(Float, nullable=True)
    strategy = Column(String(100), nullable=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    asset_type = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)  # buy/sell/neutral
    confidence = Column(Float, nullable=False)
    strategy = Column(String(100), nullable=False)
    price = Column(Float, nullable=True)
    indicators = Column(Text, nullable=True)  # JSON
    acted_on = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_signals_symbol_created", "symbol", "created_at"),
    )


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    total_equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    open_positions_value = Column(Float, nullable=False)
    daily_pnl = Column(Float, nullable=True)
    total_pnl = Column(Float, nullable=True)
    drawdown_pct = Column(Float, nullable=True)
    win_rate = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)


class MarketAlert(Base):
    __tablename__ = "market_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    price = Column(Float, nullable=True)
    triggered = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OHLCVBar(Base):
    """
    Persistent OHLCV bar storage.
    Acts as a long-lived cache (days to weeks) so data is not
    re-downloaded on every restart.
    """
    __tablename__ = "ohlcv_bars"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    stored_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ohlcv_symbol_tf_ts", "symbol", "timeframe", "timestamp", unique=True),
        Index("ix_ohlcv_stored_at", "stored_at"),
    )


class PatternObservationDB(Base):
    """
    Persistenza della coda di osservazione pattern.
    Creata automaticamente da create_all() all'avvio.
    """
    __tablename__ = "pattern_observations"

    id              = Column(String(36), primary_key=True)   # uuid
    symbol          = Column(String(20), nullable=False, index=True)
    pattern_name    = Column(String(60), nullable=False)
    direction       = Column(String(10), nullable=False)     # bullish|bearish|neutral
    status          = Column(String(12), nullable=False)     # forming|confirmed|failed|expired
    confidence      = Column(Float, nullable=True)
    timeframe       = Column(String(10), nullable=True)
    bars_involved   = Column(Integer, nullable=True)
    invalidation_price  = Column(Float, nullable=True)
    confirmation_price  = Column(Float, nullable=True)
    target_price    = Column(Float, nullable=True)
    forming_since   = Column(DateTime, nullable=True)
    confirmed_at    = Column(DateTime, nullable=True)
    failed_at       = Column(DateTime, nullable=True)
    metadata_json   = Column(Text, nullable=True)            # JSON dict
    created_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_pattern_obs_symbol_status", "symbol", "status"),
        Index("ix_pattern_obs_created_at",    "created_at"),
    )


class AIConfig(Base):
    """
    Persists AutoConfigResult and AI state per symbol.
    Allows the AI to restore its last known configuration after restart.
    """
    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    asset_type = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    regime = Column(String(20), nullable=True)
    hurst = Column(Float, nullable=True)
    dominant_period = Column(Integer, nullable=True)
    recommended_strategy = Column(String(50), nullable=True)
    active_indicators = Column(Text, nullable=True)      # JSON list
    indicator_weights = Column(Text, nullable=True)      # JSON dict
    tuned_params = Column(Text, nullable=True)           # JSON dict
    fundamental_score = Column(Float, nullable=True)
    oscillator_for_chart = Column(String(30), nullable=True)
    confidence = Column(Float, nullable=True)
    # Serialised ML state
    meta_learner_history = Column(Text, nullable=True)   # JSON list of (fv, label)
    selector_weights = Column(Text, nullable=True)       # JSON nested dict

    __table_args__ = (
        Index("ix_ai_configs_symbol_ts", "symbol", "timestamp"),
    )
