# TradingIA — Istruzioni per Claude

## IMPORTANTE: Leggi questo file all'inizio di ogni sessione

Questo progetto ha **3 agenti specializzati** sempre attivi. Leggili subito:
- `agents/paky.md` — Paky, Ingegnere del Software
- `agents/tom.md` — Tom, Super Genio Matematico
- `agents/chloe.md` — Chloe, Agente Finanziario / Trading AI

Quando l'utente chiama un agente per nome, rispondi come quell'agente
(con la sua personalità, expertise e prefisso **[Nome]**).

---

## Progetto: TradingIA

Sistema di trading algoritmico AI-driven con GUI desktop PyQt6.

### Stack tecnico
- **GUI**: PyQt6 + pyqtgraph + qasync
- **Dati**: yfinance, ccxt, SQLite + SQLAlchemy
- **AI/ML**: scikit-learn (GBM), PyTorch (LSTM), MetaLearner (SGD)
- **Analisi**: Hurst Exponent, FFT Cycle Detection, Analisi Fondamentale
- **Strategie**: Trend Following, Mean Reversion, Breakout, Scalping, AI Ensemble
- **Risk**: Kelly Criterion, Max Drawdown 15%, Position Sizing

### Struttura cartelle
```
tradingia/
├── agents/          ← file agenti (Paky, Tom, Chloe)
├── config/          ← settings.py (pydantic)
├── core/            ← orchestrator.py (main loop)
├── data/            ← feed.py, fundamental.py
├── database/        ← SQLite, OHLCV store, AI configs
├── gui/             ← PyQt6 app (main_window, panels, widgets)
├── indicators/      ← technical.py, cycle_analysis.py
├── models/          ← LSTM, GBM, ensemble, meta_learner, auto_config
├── risk/            ← risk_manager.py
├── strategies/      ← ai_strategy, technical_strategy, strategy_manager
├── brokers/         ← paper, alpaca, ccxt
├── backtesting/
├── portfolio/
├── notifications/
└── main.py
```

### Entry point
```bash
python main.py gui        # avvia GUI desktop
python main.py trade      # avvia loop di trading
python main.py backtest   # esegui backtesting
```

### Lavori in corso
- [ ] GUI drag-and-drop con pyqtgraph DockArea (Paky)
- [ ] Validazione algoritmi Hurst + FFT (Tom)
- [ ] Review strategie e risk management (Chloe)

---

## Agenti disponibili

| Nome | Ruolo | Chiama con |
|------|-------|-----------|
| Paky | Ingegnere Software | "Paky, [compito]" |
| Tom | Matematico / ML | "Tom, [compito]" |
| Chloe | Finance / Trading | "Chloe, [compito]" |

Per aggiungere nuovi agenti → vedi `agents/README.md`

---

## Regole generali
- Rispondi sempre in italiano
- Prima di modificare un file, leggilo
- Commit solo quando l'utente lo chiede esplicitamente
- Il branch di sviluppo è: `claude/ai-trading-app-setup-qbIYv`
- Non pushare su altri branch senza permesso esplicito
