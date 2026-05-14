# TradingIA — Stato Sprint

> File aggiornato a ogni fine task significativo.
> Sostituisce le sezioni "Completato" e "Lavori in corso" che prima erano in CLAUDE.md.

## 🚧 Sprint attivo: Refactor radicale GUI Bloomberg-grade

**Decisione utente (2026-05-14):** *"Se mi rendi l'applicazione perfetta dal punto di vista grafico e funzionale ok resto con Qt, altrimenti passiamo al mobile."*

**Piano completo:** `/root/.claude/plans/la-gui-pessima-delegated-bentley.md` (può non essere disponibile in nuove sessioni — il piano operativo è duplicato qui sotto)

### ✅ Gate Review SUPERATO (2026-05-14)

L'utente ha lanciato la demo dopo il fix QShortcut e ha confermato: **"così mi piace"**. Qt vince, si prosegue con il refactor radicale. Path B mobile non attivato.

### Stato fasi piano

- [x] **Fase 0 — Sistema agenti**: 5 subagent `.claude/agents/*.md` con Opus/Sonnet + memoria persistente `agents/memory/*.md`
- [x] **Fase 0 — Compattazione doc**: split CLAUDE.md (39 LOC) → `docs/RULES.md`, `docs/STACK.md`, `docs/SPRINT.md`
- [x] **Fase 1 — GUI fondamenta + info widgets MVP**:
  - `gui/state/app_state.py` (singleton, 11 segnali Qt, bridge SignalBus)
  - `gui/styles/dark.qss` (1203 LOC, copertura completa)
  - `gui/widgets/info/` (Sparkline, KPIBadge, RegimePill, Gauge, HelpIcon)
  - `gui/widgets/top_bar.py` (Bloomberg-style 42px, 8 KPI live)
  - `gui/workspaces/dashboard.py` (demo con liveness QTimer 2s)
  - `gui/main_window.py` riscritto (372→121 LOC, zero QDockWidget)
- [x] **🚦 Gate Review — Qt VINCE** (PR #12 + #13 mergiati)
- [x] **Quality gate agenti**: Paky e Marco ora hanno regola obbligatoria di real import test + istanziazione widget prima di chiudere task (commit d13075c)
- [ ] **Fase 1.5 — Polish difetti gate review** (3 ondate, dettaglio sotto)
- [ ] Fase 2 — Workspaces rimanenti (5 file in `gui/workspaces/`)
- [ ] Fase 3 — ActivityBar verticale sinistra per switch workspace
- [ ] Fase 4 — Espansione info widgets (8 widget rimanenti)
- [ ] Fase 5 — Arricchimento panel atomici + 5 nuovi segnali in SignalBus
- [ ] Fase 6 — Fix stati pulsanti via AppState (tutti i panel)
- [ ] Smoke test finale + screenshot di benchmark

---

## 🎨 Fase 1.5 — Polish difetti gate review (PROSSIMO STEP)

Difetti identificati nello screenshot del gate review (2026-05-14, app live su Windows). Organizzati in 3 ondate per impatto/effort.

### Ondata 1 — Layout fixes (high impact, low effort, ~30 min)

**Agente delegato**: Marco

**File coinvolti**: `gui/workspaces/dashboard.py`, `gui/widgets/top_bar.py`, `gui/styles/dark.qss`

1. **Spazio enorme tra TopBar e WATCHLIST** (~50px vuoto inutile)
   - Causa probabile: `QGroupBox` titolo o margini del `_WatchlistPanel` in `dashboard.py`
   - Fix: `setContentsMargins(0, 0, 0, 0)` + `QGroupBox` con title offset corretto, o riduci `margin-top` del groupbox in QSS

2. **Bottone START troppo alto** rispetto agli altri elementi TopBar (54px contro 42px previsti)
   - Causa: padding eccessivo nel QSS `QPushButton[variant="primary"]` o `setMinimumHeight` esplicito
   - Fix: `setFixedHeight(28)` sul `_engine_btn` in `top_bar.py`, o `max-height: 28px` nella regola QSS

3. **TopBar sbilanciata verso sinistra**: dopo broker pill "63ms" un buco gigante prima del clock UTC
   - Causa: spacer expanding nel posto sbagliato
   - Fix: in `top_bar.py`, posizionare `addStretch()` PRIMA del clock, non dopo il broker pill

4. **POSIZIONI APERTE senza header colonne**
   - Causa: `_PositionsPanel` in `dashboard.py` non ha riga header
   - Fix: aggiungere `QLabel` header row con "SIMBOLO | DIR | ENTRY → CURRENT | P&L" in muted color sopra le righe

5. **Card HURST/KELLY/VOLATILITY senza bordo** — si confondono col background
   - Fix: in `_GaugeCard` (dashboard.py) aggiungere `QFrame` con `setStyleSheet("background:#161b22; border:1px solid #30363d; border-radius:4px;")` come container

6. **Posizioni mostrano `+234.50` senza valuta**
   - Fix: nel `_PositionsPanel._build_row()`, prefissa il P&L con `€`

7. **Regime divergente TopBar (H 0.62) vs AI Panel (H 0.66)**
   - Causa: due QTimer separati che generano valori diversi
   - Fix: in `dashboard.py`, il regime+hurst viene scritto in `AppState.current_regime` / `current_hurst`. AI Panel deve LEGGERE da AppState, non avere un proprio random

### Ondata 2 — AI Panel destro (medium effort, ~45 min)

**Agente delegato**: Marco

**File coinvolti**: `gui/workspaces/dashboard.py` (classe `_AIPanel`)

8. **"AI ANALYSIS" titolo ha layout strano** con linea sopra il regime pill
   - Verifica: c'è un separator o un border-top inaspettato sul groupbox? Pulisci

9. **"LONG" + "AI Prediction" mal disposti**, ▲ verde separato dal testo
   - Fix: usare un singolo `QLabel` con HTML `<span style='color:#3fb950;'>▲</span> LONG <small>AI Prediction</small>` o un widget custom compatto

10. **"Strategy: Trend4H" e "Last signal: 4m ago"** flottanti
    - Fix: avvolgerli in un footer `QFrame` con stile compact (font 9px text-muted) come metadata pinned in basso

11. **History (50 PRED.) sparkline tutta rossa**
    - Causa: la `Sparkline` ha auto-detect bull/bear basato su `values[-1] vs values[0]` — i valori demo iniziano alti e scendono → si colora rossa
    - Fix: aggiungere parametro `marker_mode="hit_miss"` alla Sparkline che mostri dot verdi/rossi per predizioni passate (hit = predizione corretta, miss = sbagliata) invece della linea singola colorata

### Ondata 3 — Polish finale (low impact, ~30 min)

**Agente delegato**: Paky (positioning/icon) + Marco (rendering)

12. **Tooltip "Percentuale di trade chiusi..."** appare a metà schermo
    - Causa: tooltip Qt6 default position può sbagliare con widget piccoli
    - Fix: implementare `event(QEvent.ToolTip)` custom nel KPIBadge che usa `QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), text)` per ancoraggio preciso

13. **Manca icona app** in alto a sinistra (default Windows)
    - Fix: creare `gui/assets/icon.png` (Marco) + `app.setWindowIcon(QIcon('gui/assets/icon.png'))` in `gui/app.py` (Paky). Suggerisco icona minimal: candela verde/rossa stilizzata su sfondo trasparente, 256×256

14. **Latency pallino "● 63ms"** non centrato verticalmente
    - Fix: in `_BrokerPill` (top_bar.py), allineare pallino con `Qt.AlignVCenter` + padding asimmetrico

15. **CHART AREA placeholder** — non è un difetto della fase 1, ma il prossimo lavoro (Fase 2) deve integrare `CandlestickChart` esistente al posto del placeholder

---

## 📐 Fase 2 — Workspaces rimanenti (~3-4 ore)

**Agente delegato**: Marco

Creare 5 nuovi workspace come `QWidget` con `QSplitter`, sul modello di `DashboardWorkspace`:

| File | Contenuto |
|------|-----------|
| `gui/workspaces/order_ticket.py` | Form ordini grande + history + broker info. Usa `BrokerPanel` esistente |
| `gui/workspaces/analysis.py` | `AIAnalysisPanel` (sinistra) + `ChartPanel` (centro) + `DataPanel` fundamental (bottom) |
| `gui/workspaces/backtest.py` | `BacktestPanel` a tutto spazio |
| `gui/workspaces/patterns.py` | `PatternPanel` (sinistra) + `ChartPanel` con overlay pattern (destra) |
| `gui/workspaces/settings.py` | Form per `.env` editing (broker config, risk params, notifications) — nuovo |

**Vincoli**: riusa i panel atomici esistenti (`ChartPanel`, `BrokerPanel`, `AIAnalysisPanel`, ecc.) istanziati una sola volta in `main_window.py` e passati per reference ai workspace che li referenziano.

---

## 🎚️ Fase 3 — ActivityBar verticale (~2 ore)

**Agente delegato**: Marco + Paky

**File nuovi**: `gui/widgets/activity_bar.py`

`ActivityBar(QFrame)` 56px verticale a sinistra con 6 icone (Dashboard, Order, Analysis, Backtest, Patterns, Settings). Emette `workspace_changed = pyqtSignal(int)`.

**Modifica main_window.py**: aggiungi `QHBoxLayout` root → `ActivityBar` + `QVBoxLayout(TopBar + QStackedWidget)`. `ActivityBar.workspace_changed` → `_stack.setCurrentIndex`.

Persisti workspace attivo + splitter sizes in `QSettings` (auto-restore al riavvio).

---

## 🧩 Fase 4 — Info widgets rimanenti (~4 ore)

**Agente delegato**: Marco

**File nuovi** in `gui/widgets/info/`:

| Widget | Uso |
|--------|-----|
| `confidence_bar.py` | Barra orizzontale 0-1 con threshold marker — pattern/AI panel |
| `bidir_bar.py` | Barra split centro bull/bear — AI prediction, sentiment |
| `heatmap.py` | Mini matrix colorata correlazioni — portfolio panel |
| `ping_indicator.py` | Dot + latency ms + uptime% — TopBar broker (rimpiazza `_BrokerPill` interno) |
| `status_dot.py` | LED idle/active/error/loading — engine panel loop status |
| `live_label.py` | Label con flash 100ms su update — prezzi live |
| `fft_mini.py` | Spettro frequenze 120x40 con peak marker — analysis panel |
| `numeric_table.py` | QTableWidget pre-configurato: monospace numeri, color coding, sparkline per riga — watchlist/positions |

---

## 🔌 Fase 5 — Arricchimento panel + signal bus (~5 ore)

**Agente delegato**: Tom (segnali) + Paky (wiring) + Marco (rendering)

### Tom — Nuovi segnali in `core/signal_bus.py`

Aggiungere:
- `ai_result = pyqtSignal(object)` — payload `AutoConfigResult` (regime, hurst, confidence, prediction)
- `kelly_update = pyqtSignal(float)` — Kelly% suggerito da RiskManager
- `regime_update = pyqtSignal(str, float)` — regime + hurst per simbolo corrente
- `loop_heartbeat = pyqtSignal(str)` — nome loop async per StatusDot ("4h_scan", "1h_scan", "trend_detect", "position_check")
- `correlation_update = pyqtSignal(object)` — matrice numpy correlazioni posizioni aperte

### Paky — Emit dei segnali nei moduli core

- `core/engine.py`: emit `loop_heartbeat(name)` ad ogni iterazione di ogni loop async
- `core/orchestrator.py`: emit `ai_result(result)` quando AutoConfig finisce
- `risk/risk_manager.py`: emit `kelly_update(kelly_pct)` quando ricalcola
- `portfolio/`: emit `correlation_update(matrix)` periodicamente

### Marco — Panel arricchiti

**`gui/panels/ai_analysis_panel.py`**:
- RegimePill in alto (legge `ai_result.regime`)
- Gauge Hurst (legge `ai_result.hurst`)
- ConfidenceBar (legge `ai_result.confidence`)
- BiDirectionalBar long/short (legge `ai_result.price_direction`)
- Gauge Kelly (collegato a `kelly_update`)
- FFTMiniChart (collegato a `CycleAnalysis.fft_spectrum`)
- Sparkline storia 50 predizioni con hit/miss markers

**`gui/panels/watchlist_panel.py`**:
- Sostituire `QTableWidget` con `numeric_table`
- Per riga: simbolo | prezzo mono | delta % colorato | sparkline 50 barre | regime pill mini

**`gui/panels/positions_panel.py`**:
- `numeric_table` con: simbolo | direzione | entry mono | current mono | P&L colorato | duration | mini-chart entry→now
- Blink rosso su SL vicino (<0.5×ATR)
- Header totals: Total P&L grande + sparkline equity curve

**`gui/panels/engine_panel.py`**:
- Rimuovere metriche equity/P&L (già in TopBar)
- StatusDot per ogni loop async (4 dot)
- Lista ultimi 10 TrendAlertEvent con micro-chart

**`gui/panels/portfolio_panel.py`** (NUOVO):
- Heatmap correlazioni
- Pie chart asset class
- Gauge drawdown corrente / max storico

---

## 🔘 Fase 6 — Fix stati pulsanti via AppState (~2 ore)

**Agente delegato**: Paky

Per ogni panel con controlli engine-dependent, applicare il pattern:

```python
state = AppState.instance()
state.engine_running_changed.connect(self._on_engine_state)
self._on_engine_state(state.engine_running)  # init

def _on_engine_state(self, running: bool):
    self._btn_X.setEnabled(running)
    # ecc.
```

**Casi specifici da risolvere**:
- `positions_panel.py`: Buy/Sell/CloseAll abilitati solo se engine_running
- `broker_panel.py` (riga 483-505): Test button con loading state via `setProperty("loading", True)` + QSS `[loading="true"]`
- `data_panel.py`: quick-pick buttons (AAPL/BTC/EUR-USD/S&P) con stato "selected" via `setProperty("active", True)`
- `pattern_panel.py`: Clear button disabled se tabella vuota
- TopBar start/stop + EnginePanel start/stop button: condividono lo stesso `QAction` globale per essere sempre sincronizzati

---

## 📋 Per riprendere il lavoro in una nuova sessione

Tutto ciò che serve a una nuova sessione di Claude Code per continuare:

1. **Leggi** `CLAUDE.md` (3KB, sa già che parlare solo con Max è la regola)
2. **Max legge** `agents/memory/max.md` per recuperare contesto strategico
3. **Max consulta** questo file (`docs/SPRINT.md`) per lo stato fasi
4. **Punto di ripartenza naturale**: **Fase 1.5 Ondata 1** (delegare a Marco)
5. **File già committati su main**:
   - PR #11, #12, #13 mergiati
   - Branch `claude/review-project-status-YGME3` può essere usato come dev branch continuativo

**Quality gate da non scordare** (commit d13075c):
- Paky e Marco devono sempre eseguire real import test + istanziazione widget prima di chiudere un task GUI
- Vedi `.claude/agents/paky.md` e `.claude/agents/marco.md` sezione "PRIMA di dichiarare il task completato"

**Path B (fallback mobile)** — non attivato, gate review superato. Resta documentato nel piano `/root/.claude/plans/la-gui-pessima-delegated-bentley.md` sezione G se in futuro servirà.

---

## ✅ Sprint completati (storico)

### Sprint GUI Fase 1 — Bloomberg-grade demo (2026-05-14)
- AppState singleton (11 segnali Qt, bridge SignalBus)
- 5 info widget MVP (Sparkline, KPIBadge, RegimePill, Gauge, HelpIcon)
- TopBar Bloomberg-style 42px con 8 KPI live
- DashboardWorkspace con liveness simulation QTimer
- main_window.py riscritto (372→121 LOC)
- dark.qss 1203 LOC copertura completa
- Quality gate import test obbligatorio per Paky/Marco
- **Gate review utente: SUPERATO** ("così mi piace")

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
- `QShortcut`/`QAction` da `QtGui` (NON `QtWidgets`, al contrario di PyQt5)
