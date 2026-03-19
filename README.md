# TradingIA ⚡

**AI-powered multi-asset trading system** supporting stocks, forex, crypto, commodities and indices.

## Features

| Module | Description |
|--------|-------------|
| **AI Models** | LSTM + Attention, Gradient Boosting Ensemble |
| **Strategies** | Trend Following, Mean Reversion, Breakout, Scalping, AI Ensemble |
| **Instruments** | Stocks, Forex, Crypto, Commodities, Indices |
| **Indicators** | 30+ technical indicators (RSI, MACD, BB, Ichimoku, Stochastic, ATR, VWAP...) |
| **Risk Manager** | Kelly sizing, trailing stops, drawdown circuit-breaker, portfolio heat |
| **Backtester** | Event-driven, Sharpe/Sortino/drawdown metrics |
| **Brokers** | Alpaca, CCXT (100+ exchanges), Paper trading |
| **Dashboard** | FastAPI + WebSocket real-time dashboard |
| **Notifications** | Telegram + Email alerts |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure (optional)
cp .env.example .env
# Edit .env with your API keys

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

## Architecture

```
tradingia/
├── main.py                    # CLI entry point
├── config/settings.py         # All configuration
├── data/feed.py               # Universal data feed (yfinance + ccxt)
├── indicators/technical.py    # 30+ technical indicators
├── models/
│   ├── lstm_model.py          # LSTM + Attention (PyTorch)
│   ├── random_forest_model.py # Gradient Boosting
│   └── ensemble_model.py      # Weighted ensemble
├── strategies/
│   ├── ai_strategy.py         # AI-driven signals
│   ├── technical_strategy.py  # Rule-based strategies
│   └── strategy_manager.py    # Multi-strategy orchestration
├── risk/risk_manager.py       # Position sizing + risk control
├── backtesting/backtester.py  # Event-driven backtester
├── portfolio/portfolio_manager.py  # Real-time P&L tracking
├── brokers/
│   ├── alpaca_broker.py       # Alpaca Markets
│   ├── ccxt_broker.py         # All crypto exchanges
│   └── paper_broker.py        # Simulated trading
├── dashboard/api.py           # FastAPI + WebSocket dashboard
├── notifications/notifier.py  # Telegram + Email
└── core/orchestrator.py       # Main trading loop
```

## Supported Instruments

- **Stocks**: AAPL, MSFT, GOOGL, NVDA, TSLA, META, SPY, QQQ + any ticker
- **Forex**: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF + all majors
- **Crypto**: BTC, ETH, BNB, SOL, XRP, ADA + any CCXT-supported pair
- **Commodities**: Gold, Silver, Crude Oil, Natural Gas, Wheat, Corn
- **Indices**: S&P 500, DJIA, NASDAQ, FTSE 100, Nikkei 225

## Trading Strategies

| Strategy | Timeframe | Description |
|----------|-----------|-------------|
| **AI Ensemble** | 1h | LSTM + Gradient Boost combined |
| **Trend Following** | 1h | EMA cross + MACD + RSI filter |
| **Mean Reversion** | 1h | Bollinger Bands + RSI extremes |
| **Breakout** | 1d | Donchian channel + volume surge |
| **Scalping** | 5m | VWAP + Stochastic + RSI |

## Risk Management

- **Position Sizing**: Kelly Criterion (fractional) scaled by signal confidence
- **Stop Loss**: ATR-based (2×ATR) with optional trailing stops
- **Take Profit**: ATR-based (3×ATR) for 1.5:1 R/R minimum
- **Drawdown Limit**: Trading halts at configurable max drawdown (default 15%)
- **Portfolio Heat**: Max concurrent risk exposure per portfolio %

## Dashboard

Open `http://localhost:8080` after starting the trading engine:
- Real-time portfolio equity, P&L, drawdown
- Live open positions with unrealized P&L
- Signal feed from all strategies
- Trade history with performance metrics
- REST API at `/api/*` and WebSocket at `/ws`

## Configuration

All settings in `config/settings.py` can be overridden via environment variables or `.env` file.

```python
# Risk
RISK_MAX_PORTFOLIO_RISK_PCT=2.0    # % capital at risk per trade
RISK_MAX_DRAWDOWN_PCT=15.0          # halt if drawdown exceeds
RISK_MAX_OPEN_POSITIONS=10

# ML
ML_MIN_CONFIDENCE=0.6              # minimum signal confidence
ML_LOOKBACK_WINDOW=60              # LSTM input bars
```

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading financial instruments involves significant risk of loss. Past performance does not guarantee future results. Always use paper trading mode first and never risk more than you can afford to lose.
