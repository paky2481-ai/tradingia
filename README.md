# TradingIA

**Sistema di trading algoritmico AI-driven con interfaccia desktop PyQt6.**
Completamente automatico, con override manuale, analisi AI in tempo reale,
riconoscimento pattern tecnici e retraining notturno dei modelli.

---

## Avvio rapido

```bash
# Installa dipendenze
pip install -r requirements.txt

# Copia e configura le credenziali
cp .env.example .env
# → Apri .env e inserisci le tue API key (broker, Telegram, ecc.)

# Lancia GUI (paper trading, €100.000)
python main.py gui

# Avvia il motore di trading headless (senza GUI, ad es. su server)
python main.py trade

# Esegui un backtest
python main.py backtest

# Training iniziale completo dei modelli AI
python main.py train --full

# Retraining incrementale manuale (ultimi 90 giorni)
python main.py train --incremental
```

---

## Broker supportati

| Broker | Tipo | Account demo | Strumenti |
|--------|------|-------------|-----------|
| **Paper** | Simulato interno | Sempre disponibile | Tutti (prezzi da yfinance) |
| **IG Markets** | CFD / Spread Betting | Gratuito | Forex, Indici, Oro, Petrolio |
| **OANDA** | Forex broker | Gratuito (practice) | Forex, XAU/USD |
| Alpaca | Azioni USA | Gratuito | Azioni, ETF USA |
| CCXT | Crypto | Sandbox | 100+ exchange crypto |

### Configurare IG Markets

1. Crea conto **demo gratuito** su [ig.com/it](https://www.ig.com/it/trading-account/demo-account)
2. Vai su [labs.ig.com](https://labs.ig.com) → My Applications → crea nuova app → copia la API Key

```env
BROKER_ACTIVE_BROKER=ig
BROKER_IG_API_KEY=la_tua_api_key
BROKER_IG_USERNAME=la_tua_email
BROKER_IG_PASSWORD=la_tua_password
BROKER_IG_ACCOUNT_TYPE=demo
```

### Configurare OANDA

1. Crea conto **practice gratuito** su [oanda.com](https://www.oanda.com/it-it/)
2. MyAccount → Manage API Access → Generate new token
3. Copia l'Account ID (formato: `101-004-XXXXXXX-001`)

```env
BROKER_ACTIVE_BROKER=oanda
BROKER_OANDA_API_TOKEN=il_tuo_token
BROKER_OANDA_ACCOUNT_ID=101-004-XXXXXXX-001
BROKER_OANDA_ENVIRONMENT=practice
```

---

## Architettura

```
python main.py trade
        │
        └─ TradingOrchestrator (asyncio, 6 loop paralleli)
              ├─ _main_loop              → scan completo ogni 60s
              │    ├─ fetch OHLCV tutti i simboli (1h, 4h, 1d)
              │    ├─ StrategyManager.evaluate_all()
              │    │    ├─ AutoConfig (regime, TF ottimale, param tuning)
              │    │    ├─ PatternStrategy / TrendFollowing / MeanReversion...
              │    │    ├─ AIStrategy (LSTM + GBM ensemble)
              │    │    └─ MetaLearner (conferma / veto segnali)
              │    ├─ RiskManager.evaluate() → position sizing Kelly
              │    └─ Broker.place_order()
              │
              ├─ _position_monitor_loop  → SL/TP/trailing stop ogni 10s
              ├─ _daily_reset_loop       → reset statistiche giornaliere
              ├─ _nightly_retrain_loop   → retraining modelli alle 02:05 UTC
              ├─ _pattern_watchlist_loop → pattern su watchlist ogni 5 min
              └─ _pattern_position_loop  → pattern di inversione su posizioni ogni 30s

        SignalBus (singleton)
              → ponte thread-safe asyncio ↔ PyQt6

        TradingMainWindow (PyQt6 + qasync)
              ├─ [Sinistra]  EnginePanel       → stato motore + controlli
              ├─ [Sinistra]  WatchlistPanel    → quote live multi-asset
              ├─ [Centro]    ChartPanel        → grafico candlestick + oscillatori
              ├─ [Destra]    AIAnalysisPanel   → regime, Hurst, FFT, fondamentali
              ├─ [Destra]    DataPanel         → loader dati storici
              ├─ [Basso]     PositionsPanel    → posizioni live + trading manuale
              ├─ [Basso]     PatternPanel      → coda pattern in osservazione
              ├─ [Basso]     BacktestPanel     → runner backtest
              └─ [Basso]     LogPanel          → log colorato in tempo reale
```

---

## Strumenti monitorati (default)

| Categoria | Simboli |
|-----------|---------|
| **Azioni** | AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, SPY, QQQ, IWM |
| **Forex** | EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF, USD/CAD, NZD/USD |
| **Crypto** | BTC-USD, ETH-USD, BNB-USD, SOL-USD, XRP-USD, ADA-USD, AVAX-USD |
| **Commodity** | Oro (GC=F), Argento (SI=F), Petrolio (CL=F), Gas Naturale (NG=F), Mais (ZC=F), Grano (ZW=F) |
| **Indici** | S&P 500, Dow Jones, NASDAQ, FTSE 100, Nikkei 225 |

Aggiungibili via `.env`: `STOCK_SYMBOLS`, `FOREX_PAIRS`, `CRYPTO_SYMBOLS`, ecc.

---

## Strategie

| Nome | Logica | Regime ideale |
|------|--------|--------------|
| **Trend Following** | EMA cross + MACD + RSI 45–65 | Trending (Hurst > 0.55) |
| **Mean Reversion** | Bollinger Bands + RSI estremi | Ranging (Hurst < 0.45) |
| **Breakout** | Donchian channels + volume | Breakout imminente |
| **Scalping** | VWAP + Stochastic + RSI | Intraday 5m |
| **AI Ensemble** | LSTM 40% + RandomForest 60% | Tutti i regimi |
| **Pattern Recognition** | 27 pattern candlestick + chart | Tutti i regimi |

`AutoConfig` seleziona automaticamente la strategia ottimale per ogni strumento ogni ora, basandosi sull'analisi di regime (Hurst, FFT, fondamentali).

---

## Pattern Recognition

Rilevamento continuo su **due thread separati**:

- **Watchlist loop** (ogni 5 min): scansiona tutti gli strumenti in cerca di pattern in formazione → quando confermati, genera segnali di apertura ordine
- **Position loop** (ogni 30s): cerca pattern di inversione su posizioni aperte → chiusura anticipata se pattern bearish su long (o viceversa)

**Pattern candlestick (20):**
Single: Doji, Hammer, Shooting Star, Inverted Hammer, Hanging Man, Bullish/Bearish Marubozu, Spinning Top
Double: Bullish/Bearish Engulfing, Harami, Piercing Line, Dark Cloud Cover, Tweezer Top/Bottom
Triple: Morning Star, Evening Star, Three White Soldiers, Three Black Crows

**Chart pattern (7):**
Double Top/Bottom, Head & Shoulders, Inverse H&S,
Ascending/Descending/Symmetrical Triangle, Bull/Bear Flag, Rising/Falling Wedge

**Ciclo di vita osservazione:**
```
FORMING → pattern rilevato, attesa conferma (breakout del livello chiave)
       ↓
CONFIRMED → prezzo ha rotto il livello → genera TradeSignal
FAILED    → prezzo ha violato l'invalidation price
EXPIRED   → ttl_bars barre senza conferma
```

**Backtesting pattern:**
```bash
python -c "
from backtesting.pattern_backtester import PatternBacktester
# df = DataFrame OHLCV caricato...
bt = PatternBacktester()
results = bt.run(df, symbol='AAPL', timeframe='1h')
for r in results:
    print(r)  # hit_rate, avg_move%, confirmation_rate, equity_curve
"
```

---

## AI Pipeline

```
OHLCV (yfinance / IG / OANDA / CCXT)
  │
  ├─ TechnicalIndicators.compute_all()   → 50+ indicatori
  ├─ HurstExponent.compute()             → H: trending / ranging / choppy
  ├─ DominantCycle.fft_period()          → ciclo dominante FFT (4–50 barre)
  ├─ FundamentalFeed.get_fundamentals()  → P/E, ROE, rate differential, stagionalità
  │    ├─ Fonte 1: yfinance (free)
  │    ├─ Fonte 2: Alpha Vantage (free, 25 req/day)
  │    └─ Fonte 3: Financial Modeling Prep (free, 250 req/day)
  ├─ TimeframeSelector.select()          → TF ottimale (1h / 4h / 1d) per simbolo
  ├─ AutoConfig.run()                    → regime + strategia + parametri ottimali
  │    └─ grid search walk-forward 300 barre
  ├─ EnsembleModel.predict()             → RandomForest 60% + LSTM 40%
  └─ MetaLearner.predict()               → SGD online (13 feature), conferma/veto

→ TradeSignal → PatternObserver (conferma pattern) → RiskManager → Broker
```

**Retraining automatico:**
- Ogni notte alle 02:05 UTC: retraining incrementale su ultimi 90 giorni
- `python main.py train --full`: training su tutti i dati disponibili (fino a 730 giorni hourly)
- Se il sistema era spento durante la finestra notturna, recupera al prossimo avvio

---

## Risk Management

| Parametro | Default | `.env` |
|-----------|---------|--------|
| Rischio per trade | 2% capitale | `RISK_MAX_PORTFOLIO_RISK_PCT` |
| Max drawdown (circuit breaker) | 15% | `RISK_MAX_DRAWDOWN_PCT` |
| Max posizioni aperte | 10 | `RISK_MAX_OPEN_POSITIONS` |
| Max size per posizione | 10% portafoglio | `RISK_MAX_POSITION_SIZE_PCT` |
| Kelly fraction | 0.25 | `RISK_KELLY_FRACTION` |
| Trailing stop | 1.5% | `RISK_TRAILING_STOP_PCT` |

**Circuit breaker**: se drawdown ≥ 15% → engine si ferma → notifica Telegram.

---

## Notifiche Telegram

Il bot invia:
- Engine avviato/fermato
- Ogni trade aperto: simbolo, direzione, entry, SL, TP, rischio %
- Ogni trade chiuso: P&L realizzato
- Pattern confermati ad alta confidenza
- Circuit breaker drawdown

**Setup:**
1. [@BotFather](https://t.me/BotFather) → `/newbot` → copia token
2. [@userinfobot](https://t.me/userinfobot) → copia chat ID

```env
NOTIFY_TELEGRAM_TOKEN=xxx
NOTIFY_TELEGRAM_CHAT_ID=yyy
```

---

## Configurazione completa `.env`

```env
# ── Broker ─────────────────────────────────────────────
BROKER_ACTIVE_BROKER=paper          # paper | ig | oanda | alpaca | ccxt

# IG Markets
BROKER_IG_API_KEY=
BROKER_IG_USERNAME=
BROKER_IG_PASSWORD=
BROKER_IG_ACCOUNT_TYPE=demo

# OANDA
BROKER_OANDA_API_TOKEN=
BROKER_OANDA_ACCOUNT_ID=
BROKER_OANDA_ENVIRONMENT=practice

# ── Dati fondamentali (fonti gratuite) ─────────────────
DATA_ALPHA_VANTAGE_KEY=             # alphavantage.co (25 req/day free)
DATA_FMP_API_KEY=demo               # financialmodelingprep.com (250 req/day free)

# ── Tassi banche centrali (override manuale) ───────────
FUND_RATE_USD=4.25
FUND_RATE_EUR=2.50
FUND_RATE_GBP=4.50
FUND_RATE_JPY=0.50

# ── Risk Management ────────────────────────────────────
RISK_MAX_PORTFOLIO_RISK_PCT=2.0
RISK_MAX_DRAWDOWN_PCT=15.0
RISK_MAX_OPEN_POSITIONS=10

# ── Pattern Recognition ────────────────────────────────
PATTERN_ENABLED=true
PATTERN_MIN_CONFIDENCE=0.60
PATTERN_MIN_SIGNAL_CONFIDENCE=0.65
PATTERN_TTL_BARS=10
PATTERN_WATCHLIST_SCAN_INTERVAL_S=300
PATTERN_POSITION_SCAN_INTERVAL_S=30

# ── ML / Retraining ────────────────────────────────────
ML_NIGHTLY_RETRAIN_ENABLED=true
ML_NIGHTLY_RETRAIN_HOUR=2
ML_INCREMENTAL_TRAIN_DAYS=90

# ── Notifiche ──────────────────────────────────────────
NOTIFY_TELEGRAM_TOKEN=
NOTIFY_TELEGRAM_CHAT_ID=
```

---

## Struttura cartelle

```
tradingia/
├── main.py                          # CLI: gui | trade | backtest | train
├── .env.example                     # Template configurazione
├── config/settings.py               # Settings centralizzate (Pydantic)
│
├── agents/                          # Definizioni agenti AI (Max, Paky, Tom, Chloe)
│
├── brokers/
│   ├── paper_broker.py              # Broker simulato (nessuna credenziale)
│   ├── ig_broker.py                 # IG Markets REST API v2
│   ├── oanda_broker.py              # OANDA REST API v20
│   ├── alpaca_broker.py             # Alpaca Markets
│   └── ccxt_broker.py               # CCXT (100+ exchange crypto)
│
├── core/
│   ├── orchestrator.py              # Motore principale (6 loop async)
│   ├── pattern_observer.py          # Coda osservazione pattern (FORMING→CONFIRMED)
│   └── signal_bus.py                # Event bus Engine ↔ GUI
│
├── data/
│   ├── feed.py                      # UniversalDataFeed (yfinance, CCXT, cache)
│   └── fundamental.py               # Analisi fondamentale multi-source
│
├── database/
│   ├── models.py                    # SQLAlchemy models (Trade, Signal, Pattern...)
│   ├── ohlcv_store.py               # Storage OHLCV persistente
│   └── ai_store.py                  # Storage segnali e configurazioni AI
│
├── indicators/
│   ├── technical.py                 # 50+ indicatori tecnici
│   ├── cycle_analysis.py            # Hurst Exponent, FFT, regime detection
│   ├── patterns.py                  # PatternDetector (27 pattern)
│   └── trend_change.py              # Trend Change Detector
│
├── models/
│   ├── lstm_model.py                # LSTM PyTorch
│   ├── random_forest_model.py       # RandomForest / GBM
│   ├── ensemble_model.py            # Ensemble LSTM + GBM
│   ├── meta_learner.py              # SGD online learning (13 feature)
│   ├── auto_config.py               # Auto-tuning orario (regime + strategia)
│   ├── timeframe_selector.py        # Selezione TF ottimale (Hurst + FFT)
│   └── indicator_selector.py        # Feature importance → top-8 indicatori
│
├── strategies/
│   ├── base_strategy.py             # TradeSignal dataclass + BaseStrategy ABC
│   ├── ai_strategy.py               # AI Ensemble strategy
│   ├── technical_strategy.py        # Trend, MeanReversion, Breakout, Scalping
│   ├── pattern_strategy.py          # Pattern Recognition strategy
│   └── strategy_manager.py          # Aggregazione + MetaLearner confirmation
│
├── risk/risk_manager.py             # Kelly Criterion, SL/TP, drawdown CB
├── portfolio/portfolio_manager.py   # Tracker P&L interno, posizioni aperte
├── notifications/notifier.py        # Telegram + Email
│
├── backtesting/
│   ├── backtester.py                # Backtester event-driven generale
│   └── pattern_backtester.py        # Backtester dedicato ai pattern
│
└── gui/
    ├── app.py                       # Entry point PyQt6 + qasync
    ├── main_window.py               # Finestra principale con dock layout
    └── panels/
        ├── engine_panel.py          # Stato motore + controlli start/stop
        ├── watchlist_panel.py       # Quote live multi-asset (tab per categoria)
        ├── chart_panel.py           # Grafico candlestick + oscillatori
        ├── ai_analysis_panel.py     # Regime, Hurst, FFT, fondamentali, AI
        ├── data_panel.py            # Loader dati storici
        ├── positions_panel.py       # Posizioni live + trading manuale
        ├── pattern_panel.py         # Coda pattern (forming/confirmed/failed)
        ├── backtest_panel.py        # Runner backtest con grafico equity
        └── log_panel.py             # Log colorato in tempo reale
```

---

## Team di agenti

| Agente | Ruolo | File |
|--------|-------|------|
| **Max** | Coordinatore — interfaccia unica verso l'utente | `agents/max.md` |
| Paky | Ingegnere Software — implementazione e architettura | `agents/paky.md` |
| Tom | Matematico / ML — algoritmi, modelli, validazione | `agents/tom.md` |
| Chloe | Finance / Trading — strategie, risk, mercati | `agents/chloe.md` |

---

## ⚠️ Disclaimer

Questo software è fornito a scopo **educativo e di ricerca**. Il trading di strumenti finanziari comporta un rischio significativo di perdita del capitale. Le performance passate non garantiscono risultati futuri. **Usa sempre prima il paper trading per almeno 30 giorni prima di utilizzare denaro reale.** Non rischiare mai più di quanto puoi permetterti di perdere.
