# TradingIA

**Sistema di trading algoritmico AI-driven con interfaccia desktop PyQt6.**
Completamente automatico, con override manuale, analisi AI in tempo reale e rilevamento anticipato dei cambi di trend.

---

## Avvio rapido

```bash
# Installa dipendenze
pip install -r requirements.txt

# Copia e configura le credenziali
cp .env.example .env
# → Apri .env e inserisci le tue API key (broker, Telegram, ecc.)

# Lancia GUI + motore automatico (paper trading, €1000)
python main.py gui --autorun

# Con broker reale IG Markets demo
# (imposta BROKER_ACTIVE_BROKER=ig nel .env)
python main.py gui --autorun

# Solo GUI senza engine (analisi manuale)
python main.py gui

# Solo engine headless (senza GUI, ad es. su server)
python main.py autorun --capital 1000 --mode paper
```

---

## Broker supportati

| Broker | Tipo | Account demo | Strumenti |
|--------|------|-------------|-----------|
| **IG Markets** | CFD / Spread Betting | Gratuito | Forex, Indici (DAX, S&P 500), Oro, Petrolio |
| **OANDA** | Forex broker | Gratuito (practice) | Forex (EUR/USD, GBP/USD…), XAU/USD |
| **Paper** | Simulato interno | Sempre disponibile | Tutti (prezzi da yfinance) |
| Alpaca | Azioni USA | Gratuito | Azioni, ETF USA |
| CCXT | Crypto | Sandbox | 100+ exchange crypto |

### Configurare IG Markets (consigliato)

1. Crea conto **demo gratuito** su [ig.com/it](https://www.ig.com/it/trading-account/demo-account)
2. Vai su [labs.ig.com](https://labs.ig.com) → My Applications → **crea nuova app** → copia la API Key
3. Nel file `.env`:

```env
BROKER_ACTIVE_BROKER=ig
BROKER_IG_API_KEY=la_tua_api_key
BROKER_IG_USERNAME=la_tua_email_ig
BROKER_IG_PASSWORD=la_tua_password
BROKER_IG_ACCOUNT_TYPE=demo
```

Quando sei pronto per il live, cambia `demo` → `live` e riavvia.

### Configurare OANDA (alternativa)

1. Crea conto **practice gratuito** su [oanda.com/it-it](https://www.oanda.com/it-it/)
2. MyAccount → Manage API Access → **Generate new token**
3. MyAccount → Account Details → copia **Account ID** (formato: `101-004-XXXXXXX-001`)

```env
BROKER_ACTIVE_BROKER=oanda
BROKER_OANDA_API_TOKEN=il_tuo_token
BROKER_OANDA_ACCOUNT_ID=101-004-XXXXXXX-001
BROKER_OANDA_ENVIRONMENT=practice
```

---

## Architettura del sistema

```
python main.py gui --autorun
         │
         ├─ TradingEngine (asyncio, 5 loop paralleli)
         │    ├─ scan_loop          → segnali ogni 1H (range) / 4H (trend)
         │    ├─ trend_detect_loop  → Trend Change Detector ogni 15 min
         │    ├─ position_monitor   → controlla SL/TP ogni 30s
         │    ├─ gui_command_loop   → riceve comandi manuali dalla GUI
         │    └─ status_loop        → heartbeat ogni 30s verso GUI
         │
         ├─ SignalBus (singleton asyncio + Qt signals)
         │    → ponte thread-safe tra Engine e GUI
         │
         ├─ AccountSync (ogni 30s)
         │    → sincronizza posizioni, balance, margine dal broker reale
         │    → rileva posizioni aperte esternamente (app mobile IG)
         │
         └─ TradingMainWindow (PyQt6 + qasync)
              ├─ [Sinistra]   EnginePanel     → stato motore + trend alerts
              ├─ [Sinistra]   Watchlist       → 7 strumenti con prezzi live
              ├─ [Centro]     ChartPanel      → grafico candlestick live
              ├─ [Destra]     AIAnalysisPanel → analisi AI completa
              ├─ [Destra]     DataPanel       → carica dati storici
              ├─ [Basso]      PositionsPanel  → posizioni live + form manuale
              └─ [Basso]      LogPanel        → log colorato in tempo reale
```

---

## Strumenti monitorati

| Simbolo | Strategia | Sessione operativa (UTC) |
|---------|-----------|--------------------------|
| EUR/USD | Trend 4H  | 07:00 – 21:00 |
| GBP/USD | Trend 4H  | 07:00 – 21:00 |
| XAU/USD | Trend 4H  | 08:00 – 20:00 |
| S&P 500 | Trend 4H  | 08:00 – 21:30 |
| DAX 40  | Trend 4H  | 08:00 – 21:30 |
| EUR/GBP | Range 1H  | 07:00 – 21:00 |
| USD/JPY | Range 1H  | 07:00 – 21:00 |

Chiuso: venerdì dopo le 20:00 UTC e domenica (spread troppo ampi).

---

## Strategie

### Trend Following 4H [Tom]
- **Entry**: EMA 9 > EMA 21 > EMA 50 + MACD cross + ADX > 20 + RSI tra 45–65
- **Stop Loss**: 2× ATR sotto entry (sopra per short)
- **Take Profit**: 3× ATR → **R/R 1:1.5**
- **Breakeven**: già profittevole al **40% di win rate**

### Mean Reversion 1H [Tom + Chloe]
- **Entry**: prezzo tocca banda Bollinger + RSI < 28 (buy) o RSI > 72 (sell)
- **Filtro regime**: Hurst < 0.52 (ranging) + ADX < 25 (no trend)
- **Target**: ritorno alla media Bollinger — R/R minimo 1.2
- **Skip**: USD/JPY nelle 2h dopo comunicati BoJ/Fed

---

## Trend Change Detector — 7 segnali [Tom]

Monitora tutti gli strumenti ogni 15 minuti e segnala i cambi di trend **prima** che avvengano.

| Segnale | Come funziona | Anticipo | Peso |
|---------|--------------|----------|------|
| **RSI Divergenza** | Prezzo lower-low, RSI higher-low → inversione imminente | 3–10 barre | 20 pt |
| **MACD Divergenza** | Divergenza su histogram MACD | 3–8 barre | 18 pt |
| **EMA Convergenza** | Gap EMA9–EMA21 si restringe → cross imminente (stima barre) | 2–5 barre | 16 pt |
| **ADX Decay** | ADX era > 28 e cala da 3+ barre → trend si esaurisce | 3–6 barre | 14 pt |
| **Hurst Transition** | Hurst scende da >0.55 a <0.52 → regime cambia | variabile | 12 pt |
| **Volume Climax** | Spike volume 2× su candela hammer/shooting star | 1–3 barre | 12 pt |
| **Structure Break** | Prezzo tenta nuovo estremo ma chiude contro | 1 barra | 8 pt |

- **Alert GUI**: confidence ≥ 30 → visibile nell'EnginePanel
- **Alert Telegram**: confidence ≥ 65 **e** ≥ 3 segnali attivi → notifica forte

---

## AI Pipeline

Per ogni strumento, ogni ora:

```
OHLCV (yfinance / IG API / OANDA API)
  │
  ├─ TechnicalIndicators.compute_all()   → 40+ indicatori in un pass
  ├─ HurstExponent.compute()             → H: trending (>0.55) / ranging (<0.45)
  ├─ DominantCycle.fft_period()          → ciclo dominante FFT (4–50 barre)
  ├─ FundamentalFeed.get_score()         → score -1 → +1 (forex: rate diff)
  ├─ IndicatorSelector.select()          → top 8 indicatori per (asset, regime)
  ├─ AutoConfig.run()                    → strategia + parametri ottimali
  │    ├─ selezione strategia da regime
  │    └─ grid search walk-forward 300 barre
  ├─ EnsembleModel.predict()             → LSTM 60% + GBM 40%
  └─ MetaLearner.predict()               → SGD online, 13 feature

→ TradeSignal → RiskManager.evaluate() → OrderResult → Broker
```

---

## Portafoglio e dettagli conto

Il pannello **Posizioni** nella GUI mostra in tempo reale (aggiornato ogni 30s):

| Campo | Fonte |
|-------|-------|
| Equity / NAV | Broker (IG balance + P&L, o OANDA NAV) |
| Balance | Deposito + P&L realizzato |
| P&L non realizzato | Somma posizioni aperte |
| Margine usato | Deposito impegnato (IG) / marginUsed (OANDA) |
| Margine libero | Capital disponibile per nuovi trade |
| Posizioni aperte | Sincronizzate dal broker ogni 30s |
| Storico trade | Ultimi 50 trade chiusi |

`AccountSync` rileva automaticamente le posizioni aperte dall'app mobile IG o dalla piattaforma web — non serve riaprire nulla manualmente.

---

## Risk Management

| Parametro | Default | `.env` |
|-----------|---------|--------|
| Rischio per trade | 1% capitale | `RISK_MAX_PORTFOLIO_RISK_PCT` |
| Max drawdown | 8% | `RISK_MAX_DRAWDOWN_PCT` |
| Max posizioni aperte | 2 | `RISK_MAX_OPEN_POSITIONS` |
| Kelly fraction | 0.25 | `RISK_KELLY_FRACTION` |
| Trailing stop | 1.5% | `RISK_TRAILING_STOP_PCT` |

**Circuit breaker automatico**: se drawdown ≥ 8% → engine si ferma → notifica Telegram.

---

## Notifiche Telegram

Il bot invia:
- Engine avviato/fermato
- Ogni trade aperto: direzione, entry, SL, TP, R/R, rischio €
- Ogni trade chiuso: P&L realizzato
- Trend Alert forti (≥65% confidence)
- Circuit breaker drawdown
- Report giornaliero alle 22:00 UTC

**Setup**:
1. [@BotFather](https://t.me/BotFather) su Telegram → `/newbot` → copia token
2. [@userinfobot](https://t.me/userinfobot) → copia chat ID
3. Nel `.env`: `NOTIFY_TELEGRAM_TOKEN=...` e `NOTIFY_TELEGRAM_CHAT_ID=...`

---

## Struttura cartelle

```
tradingia/
├── main.py                          # CLI: gui | autorun | backtest | scan
├── .env.example                     # Template configurazione
├── config/settings.py               # Settings centralizzate (Pydantic)
│
├── brokers/
│   ├── ig_broker.py                 # IG Markets REST API v2 (demo + live)
│   ├── oanda_broker.py              # OANDA REST API v20 (practice + live)
│   ├── paper_broker.py              # Broker simulato (nessuna credenziale)
│   ├── alpaca_broker.py             # Alpaca Markets
│   └── ccxt_broker.py               # CCXT crypto
│
├── core/
│   ├── engine.py                    # Motore automatico (5 loop async)
│   └── signal_bus.py                # Event bus Engine ↔ GUI
│
├── indicators/
│   ├── technical.py                 # 40+ indicatori tecnici
│   ├── cycle_analysis.py            # Hurst, FFT, regime detection
│   └── trend_change.py              # Trend Change Detector (7 segnali)
│
├── strategies/
│   ├── trend_4h.py                  # EMA+MACD+ADX (trend)
│   ├── range_1h.py                  # BB+RSI+Hurst (range)
│   ├── ai_strategy.py               # AI strategy (EnsembleModel)
│   └── strategy_manager.py          # Orchestrazione multi-strategia
│
├── models/
│   ├── lstm_model.py                # LSTM + MultiheadAttention (PyTorch)
│   ├── random_forest_model.py       # Gradient Boosting Classifier
│   ├── ensemble_model.py            # Ensemble LSTM+GBM
│   ├── meta_learner.py              # SGD online learning
│   ├── indicator_selector.py        # Selezione AI indicatori
│   └── auto_config.py               # Auto-tuning orario
│
├── risk/risk_manager.py             # Kelly, SL/TP, drawdown CB
│
├── portfolio/
│   ├── portfolio_manager.py         # Tracker P&L locale
│   └── account_sync.py              # Sync broker → GUI ogni 30s
│
├── gui/
│   ├── app.py                       # Entry PyQt6 + qasync
│   ├── main_window.py               # Finestra con dock layout
│   └── panels/
│       ├── engine_panel.py          # Stato motore + trend alerts
│       ├── positions_panel.py       # Posizioni live + form manuale
│       ├── chart_panel.py           # Grafico candlestick
│       ├── watchlist_panel.py       # 7 strumenti live
│       ├── ai_analysis_panel.py     # Analisi AI completa
│       └── data_panel.py            # Loader dati storici
│
├── notifications/notifier.py        # Telegram + Email
└── backtesting/backtester.py        # Backtester event-driven
```

---

## ⚠️ Disclaimer

Questo software è fornito a scopo **educativo e di ricerca**. Il trading di strumenti finanziari comporta un rischio significativo di perdita del capitale. Le performance passate non garantiscono risultati futuri. **Usa sempre prima il paper trading per almeno 30 giorni prima di utilizzare denaro reale.** Non rischiare mai più di quanto puoi permetterti di perdere.
