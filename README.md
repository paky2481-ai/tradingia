# TradingIA

**AI-powered multi-asset trading system** supporting stocks, forex, crypto, commodities and indices.

## Features

| Module | Description |
|--------|-------------|
| **AI Models** | LSTM + Attention, Gradient Boosting Ensemble, Meta-Learner (online learning) |
| **Cycle Analysis** | Hurst exponent (R/S), FFT dominant cycle detection, market regime classification |
| **Fundamental Analysis** | Stocks (P/E, EPS, ROE), Forex (rate differential), Commodity (seasonal z-score) |
| **Indicator Selector** | AI selects the top 8 indicators per instrument type and market regime |
| **Auto-Config** | Hourly self-tuning: regime detection → strategy selection → parameter grid search |
| **Strategies** | Trend Following, Mean Reversion, Breakout, Scalping, AI Ensemble |
| **Instruments** | Stocks, Forex, Crypto, Commodities, Indices |
| **Indicators** | 40+ technical indicators (RSI, MACD, BB, Ichimoku, Stochastic, ATR, VWAP, CCI...) |
| **Risk Manager** | Kelly sizing, trailing stops, drawdown circuit-breaker, portfolio heat |
| **Backtester** | Event-driven, Sharpe/Sortino/drawdown metrics |
| **Brokers** | Alpaca, CCXT (100+ exchanges), Paper trading |
| **Desktop GUI** | PyQt6 real-time chart, AI Analysis panel, oscillator sub-chart |
| **Dashboard** | FastAPI + WebSocket real-time dashboard |
| **Notifications** | Telegram + Email alerts |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure (optional)
cp .env.example .env
# Edit .env with your API keys

# Launch desktop GUI
python main.py gui

# Paper trading (no keys needed)
python main.py trade --paper --broker paper

# Run backtests
python main.py backtest --symbol AAPL --strategy trend_following
python main.py backtest --symbol BTC-USD --strategy breakout
python main.py backtest --symbol EURUSD=X --strategy mean_reversion

# Train AI models
python main.py train --symbols "AAPL,MSFT,BTC-USD,ETH-USD"

# One-shot signal scan
python main.py scan

# Dashboard only
python main.py dashboard --port 8080
```

## How It Works — Full AI Pipeline

Every time the system evaluates a symbol, the following pipeline runs:

```
OHLCV data (yfinance / CCXT)
  │
  ├─→ TechnicalIndicators.compute_all()     40+ indicators computed in one pass
  │
  ├─→ CycleFeatures.compute_all()           Hurst exponent (R/S analysis)
  │       HurstExponent.compute()           FFT dominant cycle period (4–50 bars)
  │       DominantCycle.fft_period()        Market regime: trending / cycling / choppy
  │       MarketRegime.detect()
  │
  ├─→ FundamentalFeed.get_fundamentals()    Asset-specific fundamental data (1h cache)
  │       FundamentalScore.compute()        Score: -1.0 (bearish) → +1.0 (bullish)
  │
  ├─→ IndicatorSelector.select()            Top 8 indicators for (asset_type, regime)
  │                                         Weights updated online via EWM after outcomes
  │
  ├─→ AutoConfig.run()  [every hour]        Full auto-configuration pipeline
  │       _select_strategy()                Rule-based: regime + Hurst → strategy name
  │       _tune_params()                    Walk-forward grid search on last 300 bars
  │       MetaLearner.train()               Retrain if ≥50 samples in history
  │
  ├─→ EnsembleModel.predict()               LSTM (confidence) + GBM (confidence)
  │
  └─→ MetaLearner.predict_from_inputs()     13-dim feature vector → final signal
          [lstm_buy, lstm_sell,             SGDClassifier with partial_fit
           gbm_buy, gbm_sell,              online learning after each trade
           hurst, cycle_phase_sin/cos,
           fundamental_score,
           regime_one_hot,
           volatility_ratio, volume_ratio]

Final ModelSignal → RiskManager.evaluate() → RiskAssessment → Execution
```

### Auto-Configuration Logic

The strategy selector maps market conditions to the optimal strategy:

| Regime | Hurst | Cycle | Selected Strategy |
|--------|-------|-------|-------------------|
| trending | > 0.55 | any | Trend Following |
| cycling | < 0.45 | ≤ 20 bars | Mean Reversion |
| cycling | < 0.45 | > 20 bars | Breakout |
| choppy | any | any | Scalping (forex/crypto) |
| any | any | any | AI Ensemble (default) |

### Fundamental Score

| Asset Type | Inputs | Score Range |
|------------|--------|-------------|
| Stock | P/E, P/B, EPS growth, revenue growth, ROE, debt/equity, dividend | -1.0 → +1.0 |
| Forex | Central bank rate differential, USD-index 1-month trend (UUP ETF) | -1.0 → +1.0 |
| Commodity | Seasonal z-score vs 3-year monthly average, year-on-year % | -1.0 → +1.0 |

## Architecture

```
tradingia/
├── main.py                          # CLI entry point
├── config/settings.py               # All configuration (Pydantic BaseSettings)
├── data/
│   ├── feed.py                      # Universal data feed (yfinance + CCXT)
│   └── fundamental.py               # Fundamental data: stocks, forex, commodity
├── indicators/
│   ├── technical.py                 # 40+ technical indicators (compute_all)
│   └── cycle_analysis.py            # Hurst exponent, FFT cycle, regime detection
├── models/
│   ├── base_model.py                # Abstract BaseModel + ModelSignal dataclass
│   ├── lstm_model.py                # LSTM + MultiheadAttention (PyTorch)
│   ├── random_forest_model.py       # Gradient Boosting classifier
│   ├── ensemble_model.py            # Weighted ensemble (LSTM + GBM)
│   ├── indicator_selector.py        # AI indicator selection per (asset, regime)
│   ├── meta_learner.py              # SGDClassifier meta-model (online learning)
│   └── auto_config.py               # Hourly auto-configuration engine
├── strategies/
│   ├── base_strategy.py             # Abstract BaseStrategy + TradeSignal dataclass
│   ├── ai_strategy.py               # AI-driven signals via EnsembleModel
│   ├── technical_strategy.py        # Trend Following, Mean Reversion, Breakout, Scalping
│   └── strategy_manager.py          # Multi-strategy orchestration + meta-learner
├── risk/risk_manager.py             # Position sizing + risk control
├── backtesting/backtester.py        # Event-driven backtester
├── portfolio/portfolio_manager.py   # Real-time P&L tracking
├── brokers/
│   ├── alpaca_broker.py             # Alpaca Markets
│   ├── ccxt_broker.py               # All crypto exchanges
│   └── paper_broker.py              # Simulated trading
├── gui/
│   ├── app.py                       # PyQt6 application entry (qasync)
│   ├── main_window.py               # Dockable main window
│   ├── panels/
│   │   ├── chart_panel.py           # Chart + info bar
│   │   ├── data_panel.py            # Symbol/timeframe loader + live feed
│   │   ├── watchlist_panel.py       # Real-time multi-asset watchlist
│   │   └── ai_analysis_panel.py     # AI Analysis dock panel
│   └── widgets/
│       ├── candlestick_chart.py     # Pyqtgraph OHLCV chart (candlestick + volume + MAs)
│       └── oscillator_chart.py      # AI-selected oscillator sub-chart
├── dashboard/api.py                 # FastAPI + WebSocket dashboard
├── notifications/notifier.py        # Telegram + Email
└── core/orchestrator.py             # Main trading loop
```

## Desktop GUI

Launch with `python main.py gui`:

- **Chart panel**: Candlestick chart with volume, MA20/50/200 overlays, live tick updates
- **AI Analysis panel** (tab): After loading a symbol, click "Run AI Analysis" to see:
  - Market regime classification with Hurst gauge
  - Dominant cycle period (bars)
  - Fundamental score bar (-1 to +1)
  - Top 8 AI-selected indicators with importance weights
  - Active strategy + tuned parameters
  - Final AI signal with confidence breakdown
- **Oscillator sub-chart**: AI automatically selects and shows the most relevant oscillator (RSI, MACD, Stochastic, CCI, or MFI)
- **Watchlist**: Real-time quotes for Stocks, Crypto, Forex, Indices with 10s auto-refresh

## Supported Instruments

- **Stocks**: AAPL, MSFT, GOOGL, NVDA, TSLA, META, SPY, QQQ + any ticker
- **Forex**: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF + all majors
- **Crypto**: BTC, ETH, BNB, SOL, XRP, ADA + any CCXT-supported pair
- **Commodities**: Gold, Silver, Crude Oil, Natural Gas, Wheat, Corn
- **Indices**: S&P 500, DJIA, NASDAQ, FTSE 100, Nikkei 225

## Risk Management

- **Position Sizing**: Kelly Criterion (fractional) scaled by signal confidence
- **Stop Loss**: ATR-based (2×ATR) with optional trailing stops
- **Take Profit**: ATR-based (3×ATR) for 1.5:1 R/R minimum
- **Drawdown Limit**: Trading halts at configurable max drawdown (default 15%)
- **Portfolio Heat**: Max concurrent risk exposure per portfolio %

## Configuration

All settings in `config/settings.py` can be overridden via environment variables or `.env` file.

```bash
# Risk
RISK_MAX_PORTFOLIO_RISK_PCT=2.0     # % capital at risk per trade
RISK_MAX_DRAWDOWN_PCT=15.0          # halt if drawdown exceeds
RISK_MAX_OPEN_POSITIONS=10

# ML
ML_MIN_CONFIDENCE=0.6               # minimum signal confidence
ML_LOOKBACK_WINDOW=60               # LSTM input bars
ML_RETRAIN_INTERVAL_HOURS=24        # full model retrain frequency

# Cycle Analysis
CYCLE_TRENDING_HURST=0.55           # Hurst threshold for trending regime
CYCLE_CYCLING_HURST=0.45            # Hurst threshold for cycling regime
CYCLE_FFT_MAX_PERIOD=50             # max cycle period to detect (bars)
CYCLE_ADX_TREND_THRESHOLD=25.0      # ADX threshold for trend confirmation

# Fundamental Analysis
FUND_ENABLED_ASSET_TYPES=stock,forex,commodity
FUND_CACHE_TTL_MINUTES=60
FUND_RATE_EUR=4.25                  # ECB rate (overridable)
FUND_RATE_GBP=5.25                  # BoE rate
FUND_RATE_JPY=0.10                  # BoJ rate

# Auto-Configuration
AUTOCONF_ENABLED=true
AUTOCONF_RETUNE_INTERVAL_HOURS=1    # recalibrate every hour
AUTOCONF_TOP_N_INDICATORS=8         # indicators to select per analysis
```

## Dashboard

Open `http://localhost:8080` after starting the trading engine:
- Real-time portfolio equity, P&L, drawdown
- Live open positions with unrealized P&L
- Signal feed from all strategies
- Trade history with performance metrics
- REST API at `/api/*` and WebSocket at `/ws`

## Disclaimer

This software is for educational and research purposes only. Trading financial instruments involves significant risk of loss. Past performance does not guarantee future results. Always use paper trading mode first and never risk more than you can afford to lose.
