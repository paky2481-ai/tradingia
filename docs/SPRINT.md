# TradingIA — Stato Sprint

> File aggiornato a ogni fine task significativo.
> Sostituisce le sezioni "Completato" e "Lavori in corso" che prima erano in CLAUDE.md.

## 🚧 Sprint attivo: Refactor radicale GUI + Sistema agenti

**Decisione utente (2026-05-14):** *"Se mi rendi l'applicazione perfetta dal punto di vista grafico e funzionale ok resto con Qt, altrimenti passiamo al mobile."*

**Piano:** `/root/.claude/plans/la-gui-pessima-delegated-bentley.md`

### Stato fasi piano

- [x] **Fase 0 — Sistema agenti**: subagent `.claude/agents/*.md` con Opus/Sonnet + memoria persistente `agents/memory/`
- [x] **Fase 0 — Compattazione doc**: split CLAUDE.md in `docs/RULES.md`, `docs/STACK.md`, `docs/SPRINT.md`
- [ ] **Fase 1 — GUI fondamenta + info widgets MVP**: `gui/state/app_state.py`, `gui/styles/dark.qss`, primi 4 info widget (Sparkline, KPIBadge, RegimePill, Gauge), TopBar demo
- [ ] **🚦 Gate Review — decisione Qt vs Mobile**
- [ ] Fase 2 — Workspaces (6 file in `gui/workspaces/`)
- [ ] Fase 3 — Riscrittura `gui/main_window.py` con QStackedWidget + ActivityBar
- [ ] Fase 4 — Espansione info widgets (8 widget rimanenti)
- [ ] Fase 5 — Arricchimento panel + 5 nuovi segnali in SignalBus
- [ ] Fase 6 — Fix stati pulsanti via AppState
- [ ] Smoke test finale

---

## ✅ Sprint completati (storico)

### Sprint Pattern Recognition (T1→T9)
- Rilevamento, osservazione, backtesting pattern candlestick + chart pattern
- `PatternStrategy`, `PatternObserver`, `PatternBacktester`
- Soglie confidenza calibrate per asset class

### Sprint TimeframeSelector
- Selezione automatica TF via Hurst + FFT + autocorrelazione
- `models/timeframe_selector.py` + integrazione in pipeline AutoConfig

### Sprint FundamentalFeed multi-source
- Fallback chain: yfinance → Alpha Vantage → FMP
- `source` field per tracciabilità dati

### Sprint Training AI
- Training iniziale massiccio (tutti i dati storici)
- Retraining notturno automatico (incrementale)
- BacktestPanel GUI con progress bar + grafici equity

### Sprint Marco (5° agente)
- Aggiunto agente GUI/Grafica/DataViz: `agents/marco.md`
- Fix candlestick "doppie": `autoRange()` → `setAutoVisible(y=True)` + `setXRange()`
- MA lines: loop O(n²) → `np.convolve` (50× più veloce)

### Sprint .ui migration
- `.ui` file per tutti i 7 panel GUI principali
- Refactor a `uic.loadUi()`: PatternPanel, BacktestPanel, AIAnalysisPanel, EnginePanel, DataPanel, PositionsPanel, WatchlistPanel
- Fix `LogPanel`: `QTextEdit` → `QPlainTextEdit` + `appendHtml()`
- Rimosso monkey-patch `QLabel.also()` da AIAnalysisPanel

### Sprint IG Broker
- Integrazione REST API v2 (demo + live)
- `BrokerPanel` GUI dedicato

### Sprint AutoConfig fix
- `price_direction` ora usa 20-bar return invece di `hurst > 0.5` (evita confirmation bias)

### Sprint compatibilità PyQt6
- `contentsMargins` rimosso dai `.ui` (impostato via Python dopo `loadUi()`)
- `GraphicsLayoutWidget(background=...)` → `setBackground()` separato
- `pydantic_settings` config con `extra = "ignore"`
