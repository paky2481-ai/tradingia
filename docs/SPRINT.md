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
- [x] **Fase 1.5 — Polish difetti gate review** — completata 2026-05-15 (commit `f92bda2`, 15 fix)
- [x] **Fase 1.6 — Internazionalizzazione (IT default + EN opzionale)** — completata 2026-05-16 (commit `97e40d9`, `2357c01`, `b8239b8`, `810387a`). 187 chiavi IT=EN, 12 file refactored con `tr()`, selettore lingua in SettingsWorkspace
- [x] **Fase 2 — Workspaces rimanenti** — completata 2026-05-16 (commit `810387a`). 5 nuovi workspace, QStackedWidget 6 slot, Ctrl+1..6 shortcut, persistenza QSettings
- [ ] Fase 3 — ActivityBar verticale sinistra per switch workspace ← PROSSIMO STEP
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

## 🌐 Fase 1.6 — Internazionalizzazione IT/EN (~3 ore)

**Requisito utente (2026-05-14)**: *"Tutto in italiano predefinito con settaggio anche in inglese. Lasciamo in inglese solo i nomi tecnici riconosciuti."*

**Agente delegato**: Paky (infrastruttura) + Marco (audit testi UI + sostituzione)

### 1.6.1 — Decidere convenzione "nomi tecnici riconosciuti"

Lista stabile di termini che **restano sempre in inglese** anche in modalità IT (perché ambigui o brutti se tradotti):

**Acronimi/sigle (sempre)**: AI, ML, LSTM, RNN, RSI, MACD, ATR, FFT, VWAP, OHLC, P&L, TP, SL, BID, ASK, UTC, API, CFD, ETF, EUR, USD, GBP, JPY (ecc. valute), ms, %, €

**Concetti matematici con nome proprio**: Hurst, Kelly, Sharpe, Sortino, Calmar, Markowitz, Black-Litterman, Black-Scholes, Heston, GARCH, ARIMA

**Termini trading riconosciuti in italiano**: long, short, trend, breakout, scalping, swing, watchlist, spread, slippage, drawdown, equity, ticker, broker, leverage, margin, lot, pip

**Tipi di ordine**: BUY, SELL, STOP, LIMIT, MARKET

**Sigle di sistema**: PAPER, LIVE, DEMO, READY, ERROR, IDLE, RUNNING

### 1.6.2 — Termini da TRADURRE in modalità IT

Mapping completo (chiavi semantiche → IT → EN):

| Chiave | Italiano (default) | English |
|--------|-------------------|---------|
| `app.title` | TradingIA — Terminale di Trading | TradingIA — Trading Terminal |
| `workspace.dashboard` | Cruscotto | Dashboard |
| `workspace.order` | Ordini | Order Ticket |
| `workspace.analysis` | Analisi | Analysis |
| `workspace.backtest` | Backtest | Backtest |
| `workspace.patterns` | Pattern | Patterns |
| `workspace.settings` | Impostazioni | Settings |
| `topbar.start` | ▶ AVVIA | ▶ START |
| `topbar.stop` | ⏸ FERMA | ⏸ STOP |
| `topbar.equity` | CAPITALE | EQUITY |
| `topbar.pnl_day` | P&L OGGI | P&L DAY |
| `topbar.positions` | POSIZIONI | POS |
| `topbar.win_rate` | VITTORIE | WIN |
| `topbar.help` | Aiuto | Help |
| `regime.trending` | IN TREND | TRENDING |
| `regime.choppy` | LATERALE | CHOPPY |
| `regime.cycling` | CICLICO | CYCLING |
| `regime.unknown` | SCONOSCIUTO | UNKNOWN |
| `dashboard.watchlist` | LISTA STRUMENTI | WATCHLIST |
| `dashboard.positions_open` | POSIZIONI APERTE | OPEN POSITIONS |
| `dashboard.no_positions` | Nessuna posizione aperta. Il motore sta scansionando i mercati... | No open positions. The engine is scanning markets... |
| `dashboard.chart_placeholder` | AREA GRAFICO | CHART AREA |
| `dashboard.chart_subtitle` | Il grafico a candele verrà integrato qui | Candlestick chart will be integrated here |
| `dashboard.ai_panel` | ANALISI AI | AI ANALYSIS |
| `dashboard.confidence` | CONFIDENZA | CONFIDENCE |
| `dashboard.ai_prediction` | Previsione AI | AI Prediction |
| `dashboard.history` | STORICO (50 PRED.) | HISTORY (50 PRED.) |
| `dashboard.strategy_label` | Strategia: | Strategy: |
| `dashboard.last_signal` | Ultimo segnale: {n}m fa | Last signal: {n}m ago |
| `gauge.hurst` | ESPONENTE DI HURST | HURST EXPONENT |
| `gauge.kelly` | KELLY % | KELLY % |
| `gauge.volatility` | VOLATILITÀ | VOLATILITY |
| `positions.header.symbol` | STRUMENTO | SYMBOL |
| `positions.header.dir` | DIR | DIR |
| `positions.header.entry` | ENTRATA → CORRENTE | ENTRY → CURRENT |
| `positions.header.pnl` | P&L | P&L |
| `status.ready` | Pronto | Ready |
| `status.workspace` | Spazio di lavoro | Workspace |
| `mode.paper` | PAPER | PAPER |
| `mode.live` | LIVE | LIVE |
| `broker.connected` | Connesso · {ms}ms | Connected · {ms}ms |
| `broker.disconnected` | Disconnesso | Disconnected |
| `help.f1.title` | TradingIA — Aiuto | TradingIA — Help |
| `help.f1.body` | F1: questo aiuto · Ctrl+K: cerca · F11: schermo intero. Premi ▶ AVVIA in alto per partire. | F1: this help · Ctrl+K: search · F11: fullscreen. Press ▶ START at the top to begin. |
| `help.search.title` | Cerca comando | Command palette |
| `help.search.body` | La palette comandi sarà disponibile nelle prossime versioni. | Command palette will be available in upcoming versions. |

**Tooltip esplicativi** (sezione importante perché lunghi):

| Chiave | Italiano (default) |
|--------|-------------------|
| `tooltip.equity` | Capitale totale (cash + valore posizioni aperte). La sparkline mostra l'andamento delle ultime 50 osservazioni. |
| `tooltip.pnl_day` | Profitto/perdita realizzato + non realizzato di oggi. Resettato a mezzanotte UTC. |
| `tooltip.positions` | Posizioni attualmente aperte / massimo configurato. |
| `tooltip.win_rate` | Percentuale di trade chiusi in profitto sugli ultimi 30 giorni. |
| `tooltip.mode` | PAPER = simulato (nessun rischio). LIVE = soldi reali sul conto broker. |
| `tooltip.broker` | Latency ping al broker. <50ms ottimo, >200ms degradato. |
| `tooltip.clock` | Ora UTC corrente. I mercati usano UTC come riferimento. |
| `help.hurst.body` | Misura la persistenza di un trend. Sotto 0.4 il prezzo tende a tornare alla media (mean-reverting). Vicino a 0.5 è random walk. Sopra 0.6 c'è trend persistente. |
| `help.kelly.body` | Percentuale ottimale del capitale da rischiare in un singolo trade. Più alta = più aggressivo. Sopra il 5% considerato pericoloso. |
| `help.volatility.body` | ATR percentile rispetto allo storico 6 mesi. >0.7 = volatilità alta, prudenza. <0.3 = mercato fermo. |
| `help.confidence.body` | Quanto il modello AI è sicuro della sua previsione. Sopra 0.7 considerato affidabile. |

### 1.6.3 — Architettura i18n

**File nuovi:**
- `gui/i18n/__init__.py` — esporta `tr()` e `set_language()`
- `gui/i18n/strings.py` — modulo con dict `IT` e `EN`, funzione `tr(key, **kwargs)` con `.format()` per parametri
- `gui/i18n/it.py` e `gui/i18n/en.py` — opzionale, se i dict crescono molto

**API minimale**:
```python
# gui/i18n/strings.py
IT = {
    "topbar.equity": "CAPITALE",
    "topbar.start": "▶ AVVIA",
    "help.f1.body": "F1: questo aiuto · Ctrl+K: cerca · F11: schermo intero...",
    # ...
}
EN = {
    "topbar.equity": "EQUITY",
    "topbar.start": "▶ START",
    # ...
}

_current_dict = IT  # default IT come da requisito

def set_language(code: str) -> None:
    """code: 'it' | 'en'"""
    global _current_dict
    _current_dict = IT if code == "it" else EN

def tr(key: str, **kwargs) -> str:
    """Traduzione con interpolazione: tr('broker.connected', ms=23) -> 'Connesso · 23ms'"""
    s = _current_dict.get(key, key)  # fallback alla chiave se manca
    if kwargs:
        s = s.format(**kwargs)
    return s
```

**Aggiunta a `gui/state/app_state.py`**:
```python
language_changed = pyqtSignal(str)
_language = "it"  # default

@property
def language(self) -> str:
    return self._language

@language.setter
def language(self, v: str):
    if v != self._language:
        self._language = v
        from gui.i18n import set_language
        set_language(v)
        self.language_changed.emit(v)
```

**Persistenza** in `QSettings`:
```python
# gui/app.py al boot
from PyQt6.QtCore import QSettings
qs = QSettings("TradingIA", "TradingIA")
lang = qs.value("language", "it", type=str)
AppState.instance().language = lang
```

**Selettore lingua** in `SettingsWorkspace` (Fase 2): `QComboBox` con opzioni "Italiano" / "English" → salva in QSettings + chiama `AppState.language = ...` + **richiede restart finestra** per ritradurre i widget statici (oppure ricostruisce dinamicamente — più lavoro).

### 1.6.4 — Strategia di rollout

**Step 1 — Audit testi**: Marco scansiona tutti i file `gui/**/*.py` per stringhe hardcoded ("EQUITY", "WATCHLIST", "CHART AREA", ecc.). Output: lista completa di stringhe da sostituire con `tr()`.

**Step 2 — Crea infrastruttura**: Paky crea `gui/i18n/` con dict IT/EN basati sulla tabella sopra. Aggiunge `language` ad AppState. Boot legge QSettings.

**Step 3 — Sostituzione progressiva**: Marco sostituisce stringhe hardcoded con `tr("key")` in ordine:
1. `gui/widgets/top_bar.py` (più visibile)
2. `gui/workspaces/dashboard.py` (più testo)
3. `gui/main_window.py` (titolo, statusbar, shortcuts help)
4. Tutti gli altri panel atomici (`gui/panels/*.py`)

**Step 4 — Test**: lancia app in IT (default), verifica visivamente. Cambia setting in EN, riavvia, verifica. Tutti i tooltip in entrambe le lingue.

### 1.6.5 — Vincoli importanti

- **Nessuna libreria pesante**: NIENTE `gettext`, `babel`, `Qt Linguist`. Dict Python puro = semplice + zero deploy overhead.
- **Fallback alla chiave**: se una chiave manca dal dict, `tr()` ritorna la chiave stessa (es. `"missing.key"` invece di crash). Marco aggiunge la chiave mancante quando la trova in test.
- **No mix di lingue**: niente "STRATEGY: Trend4H" — o tutto IT ("STRATEGIA: Trend4H") o tutto EN.
- **Nomi tecnici INVARIATI**: anche in dict IT, "Hurst", "Kelly", "ATR", "LSTM", "long/short" restano in inglese (vedi sezione 1.6.1).
- **Default IT**: `_current_dict = IT` nel modulo, `qs.value("language", "it")` al boot.

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
