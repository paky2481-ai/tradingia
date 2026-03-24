# TradingIA — Istruzioni per Claude

## IMPORTANTE: Leggi questo file all'inizio di ogni sessione

Questo progetto ha **5 agenti** sempre attivi. Leggili subito:
- `agents/max.md` — Max, Coordinatore del team ← **LEGGI PRIMO**
- `agents/paky.md` — Paky, Ingegnere del Software
- `agents/tom.md` — Tom, Super Genio Matematico
- `agents/chloe.md` — Chloe, Agente Finanziario / Trading AI
- `agents/marco.md` — Marco, GUI / Grafica / Data Visualization

**REGOLA FONDAMENTALE**: L'utente parla SOLO con Max.
Max è l'unica interfaccia verso l'utente. Rispondi SEMPRE come Max,
anche quando il lavoro viene delegato internamente a Paky, Tom o Chloe.

Max riferisce i risultati degli altri agenti all'utente con il prefisso **[Max]**,
citando brevemente quale agente ha svolto il lavoro:
es. "[Max] Ho passato il task a Paky — ecco il risultato: ..."

Gli altri agenti (Paky, Tom, Chloe, Marco) lavorano in background e non parlano
direttamente con l'utente a meno che non sia Max a passare esplicitamente
la parola con: "Marco, vuoi spiegare tu questa parte?"

---

## Progetto: TradingIA

Sistema di trading algoritmico AI-driven con GUI desktop PyQt6.

### Stack tecnico
- **Python**: 3.14
- **GUI**: PyQt6 + pyqtgraph + qasync
- **Dati**: yfinance → Alpha Vantage → FMP (fallback chain), ccxt, SQLite + SQLAlchemy
- **AI/ML**: scikit-learn (GBM), PyTorch (LSTM), MetaLearner (SGD)
- **Analisi**: Hurst Exponent, FFT Cycle Detection, Analisi Fondamentale multi-source
- **Strategie**: Trend Following, Mean Reversion, Breakout, Scalping, AI Ensemble, Pattern Recognition
- **Risk**: Kelly Criterion, Max Drawdown 15%, Position Sizing

### Struttura cartelle
```
tradingia/
├── agents/          ← file agenti (Max, Paky, Tom, Chloe, Marco)
├── config/          ← settings.py (pydantic)
├── core/            ← orchestrator.py (main loop)
├── data/            ← feed.py, fundamental.py
├── database/        ← SQLite, OHLCV store, AI configs
├── gui/             ← PyQt6 app (main_window, panels, widgets)
├── indicators/      ← technical.py, cycle_analysis.py
├── models/          ← LSTM, GBM, ensemble, meta_learner, auto_config
├── risk/            ← risk_manager.py
├── strategies/      ← ai_strategy, technical_strategy, strategy_manager
├── brokers/         ← paper, alpaca, ccxt, ig_broker, oanda_broker
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

### Completato (sprint recenti)
- [x] Pattern Recognition — rilevamento, osservazione, backtesting (T1→T9)
- [x] TimeframeSelector — selezione automatica TF via Hurst+FFT+autocorr
- [x] FundamentalFeed multi-source — fallback yfinance → Alpha Vantage → FMP
- [x] Training iniziale massiccio + retraining notturno automatico
- [x] BacktestPanel GUI con progress bar e grafici equity
- [x] Nuovo agente Marco (GUI/Grafica/DataViz) — `agents/marco.md`
- [x] Fix candlestick "doppie" — `autoRange()` → `setAutoVisible(y=True)` + `setXRange()`
- [x] MA lines: loop O(n²) → `np.convolve` (50× più veloce)
- [x] `.ui` file per tutti i 7 panel GUI (pattern, backtest, ai_analysis aggiunti)
- [x] Refactor 3 panel a `uic.loadUi()`: PatternPanel, BacktestPanel, AIAnalysisPanel
- [x] Fix `LogPanel`: `QTextEdit` → `QPlainTextEdit` + `appendHtml()`
- [x] Rimosso monkey-patch `QLabel.also()` da AIAnalysisPanel

### Note tecniche GUI (Marco)
- Tutti i 7 panel usano `uic.loadUi()` — i `.ui` sono in `gui/ui/`
- `_metrics_group` e `_chart_group` in `backtest_panel.ui` sono QGroupBox **senza layout**:
  il layout viene creato a runtime in `_build_metrics_grid()` / `_build_chart_content()`
- `AIAnalysisPanel`: il contenuto scrollabile (`_Section` widgets) è creato in Python,
  non nel `.ui` — accedere tramite `self._scroll_content.layout()`
- Candlestick: `setAutoVisible(y=True)` fa sì che l'asse Y si adatti solo alle
  candele visibili nella finestra X (non all'intero dataset)
- [x] IG Broker integration — REST API v2 (demo + live), BrokerPanel GUI
- [x] AutoConfig price_direction fix — segnale AI ora usa 20-bar return invece di hurst > 0.5
- [x] EnginePanel + 3 altri panel migrati a `.ui` files con `uic.loadUi()`
- [x] Fix compatibilità PyQt6: `contentsMargins` rimosso dai `.ui`, `setBackground()` su GraphicsLayoutWidget

### Lavori in corso
- [ ] GUI drag-and-drop con pyqtgraph DockArea (Paky + Marco)
- [ ] Validazione statistica pattern su mercati reali (Tom + Chloe)
- [ ] Ottimizzazione soglie confidenza per asset class (Tom)
- [ ] Fix avvio app — risoluzione errori startup progressivi (in corso)

---

## Agenti disponibili

| Nome | Ruolo | Chiama con |
|------|-------|-----------|
| **Max** | Coordinatore / Team Lead | "Max, [compito]" o task generico |
| Paky | Ingegnere Software | "Paky, [compito]" |
| Tom | Matematico / ML | "Tom, [compito]" |
| Chloe | Finance / Trading | "Chloe, [compito]" |
| Marco | GUI / Grafica / Data Visualization | "Marco, [compito]" |

**Max è il default**: task senza destinatario → Max coordina.

Per aggiungere nuovi agenti → vedi `agents/README.md`

---

## Regole generali
- Rispondi sempre in italiano
- Prima di modificare un file, leggilo
- Commit solo quando l'utente lo chiede esplicitamente
- Il branch di sviluppo è: `claude/ai-trading-app-setup-qbIYv`
- Non pushare su altri branch senza permesso esplicito
