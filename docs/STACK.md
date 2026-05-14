# TradingIA — Stack Tecnico e Struttura

Sistema di trading algoritmico AI-driven con GUI desktop PyQt6.

## Stack tecnico

| Layer | Tecnologie |
|-------|-----------|
| **Linguaggio** | Python 3.12 (in `.venv312`), no 3.14 (torch DLL rotto) |
| **GUI** | PyQt6 + pyqtgraph + qasync (loop Qt+asyncio condiviso) |
| **Dati** | yfinance → Alpha Vantage → FMP (fallback chain), ccxt, SQLite + SQLAlchemy |
| **AI / ML** | scikit-learn (GBM/RF), PyTorch (LSTM), SGD online (MetaLearner) |
| **Analisi** | Hurst Exponent (R/S), FFT cycle detection, analisi fondamentale multi-source |
| **Strategie** | Trend Following, Mean Reversion, Breakout, Scalping, AI Ensemble, Pattern Recognition |
| **Risk** | Kelly Criterion fractional, Max Drawdown 15%, Position Sizing dinamico |
| **Broker** | Paper (default), IG Markets (REST v2), OANDA, Alpaca, CCXT crypto |

## Struttura cartelle

```
tradingia/
├── .claude/agents/  ← subagent Claude Code (model+workflow)
├── agents/          ← specifiche narrative agenti (Max, Paky, Tom, Chloe, Marco)
│   └── memory/      ← memoria operativa persistente per agente
├── docs/            ← documentazione modulare (RULES, STACK, SPRINT)
├── config/          ← settings.py (pydantic)
├── core/            ← orchestrator.py, engine.py, signal_bus.py, pattern_observer.py
├── data/            ← feed.py (OHLCV), fundamental.py (multi-source)
├── database/        ← SQLite, OHLCV store, AI configs (SQLAlchemy)
├── gui/             ← PyQt6 app (main_window, panels, widgets, ui, styles)
│   ├── panels/      ← 9 panel (engine, watchlist, ai_analysis, data, broker, positions, log, backtest, pattern)
│   ├── widgets/     ← candlestick_chart, oscillator_chart, (info/ in arrivo)
│   ├── ui/          ← file Qt Designer .ui per 7 panel
│   └── styles/      ← QSS dark theme
├── indicators/      ← technical.py (RSI/MACD/Bollinger/ATR), cycle_analysis.py (Hurst/FFT), patterns.py, trend_change.py
├── models/          ← LSTM, GBM/RF, ensemble, meta_learner, auto_config, indicator_selector, timeframe_selector
├── risk/            ← risk_manager.py (Kelly, MaxDD, position sizing)
├── strategies/      ← trend_4h, range_1h, technical_strategy (TF/MR/BO/SC), ai_strategy, pattern_strategy, strategy_manager
├── brokers/         ← paper, alpaca, ccxt, ig_broker (538 LOC), oanda_broker (475 LOC)
├── backtesting/     ← Backtester core + pattern_backtester
├── portfolio/       ← gestione portafoglio multi-position
├── notifications/   ← Telegram, email alerts
└── main.py          ← entry point CLI (click)
```

## Architettura runtime

GUI e Engine condividono lo stesso event loop asyncio via `qasync`. Comunicazione GUI ↔ Engine passa per `core/signal_bus.py` (eventi `EngineStatusEvent`, `TrendAlertEvent`, `PatternAlertEvent`, comandi `OpenTradeCommand`, `CloseTradeCommand`).

```
python main.py gui --autorun
       │
       ├─ QApplication + qasync event loop
       ├─ TradingMainWindow
       └─ TradingEngine (asyncio, 5 loop paralleli):
           ├─ scan 4H ogni 4h
           ├─ scan 1H ogni 1h
           ├─ TrendChangeDetector ogni 15min
           ├─ position checker ogni 30s (SL/TP)
           └─ engine status emit ogni 30s → GUI status bar
```

## Strumenti operativi (live engine)

7 strumenti hardcoded in `core/engine.py::INSTRUMENTS`:

| Simbolo | Display | Strategia | Asset class |
|---------|---------|-----------|-------------|
| EURUSD=X | EUR/USD | trend_4h | forex |
| GBPUSD=X | GBP/USD | trend_4h | forex |
| XAUUSD=X | XAU/USD | trend_4h | commodity |
| ^GSPC | S&P 500 | trend_4h | index |
| ^GDAXI | DAX 40 | trend_4h | index |
| EURGBP=X | EUR/GBP | range_1h | forex |
| JPY=X | USD/JPY | range_1h | forex |

## Configurazione

Pydantic Settings (`config/settings.py`) legge `.env` con prefissi:
`DB_*`, `BROKER_*`, `DATA_*`, `RISK_*`, `ML_*`, `CYCLE_*`, `FUND_*`, `AUTOCONFIG_*`, `TFS_*`, `PATTERN_*`, `NOTIF_*`.

La Config principale ha `extra = "ignore"` per evitare crash su variabili extra.
