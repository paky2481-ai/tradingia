# Paky — Memoria operativa

> File aggiornato dall'agente Paky stesso al termine di ogni task.
> Paky legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-18: Fase A.1 — Filo conduttore frontend/backend. (1) WatchlistPanel click → AppState.current_symbol. (2) Nuovo segnale `current_scan_symbol(str,str)` in SignalBus + `emit_current_scan_symbol`. (3) Emit nei 3 loop engine (4h_scan, trend_detect, position_check). (4) AIAnalysisPanel + ChartPanel ascoltano current_symbol_changed: aggiornano titolo/info bar. (5) OrderTicket: QLineEdit→QComboBox popolato da INSTRUMENTS, sync bidirezionale con AppState. (6) TopBar: chip simbolo human-readable tra engine btn e KPI. 4/4 quality gate PASS.
- 2026-05-16: Fase 5.1 — Emit 5 segnali SignalBus in moduli core: `emit_loop_heartbeat` in `_scan_loop`/`_trend_detect_loop`/`_position_monitor_loop`/`_status_loop` di engine.py; `emit_ai_result` in `_scan_cycle` orchestrator dopo `evaluate_all`; `emit_kelly_update` in `_size_position` risk_manager con guard delta>0.005; `emit_regime_update` standalone in `auto_config._pipeline` dopo cycle analysis; `emit_correlation_update` via nuovo metodo `_emit_correlation_if_ready` in engine quando ≥2 posizioni in cache. Quality gate: PASS.
- 2026-05-16: Fase 3 — ActivityBar integrata in main_window.py: layout root cambiato da QVBoxLayout a QHBoxLayout (ActivityBar 56px | right_col con TopBar+Stack). Fallback graceful se ActivityBar non disponibile (VBoxLayout + warning stdout). _switch_workspace ora chiama set_active(idx) per sync visivo. Quality gate: PASS (has_activity_bar=True, stack=6).
- 2026-05-16: Fase 2 — SettingsWorkspace (gui/workspaces/settings.py, ~230 LOC): sezioni Generale/Broker/Rischio/Info, persistenza .env manuale+dotenv fallback, BrokerPanel popup. main_window.py esteso a 6 workspace con import graceful per workspace Marco, shortcut Ctrl+1..6, persistenza QSettings geometry+active_workspace. 43 chiavi nuove in strings.py IT+EN (incluse workspace.order_ticket e workspace.subtitle.*). Quality gate: PASS.
- 2026-05-15: Fase 1.6.2 — creata infrastruttura gui/i18n/ con 136 chiavi IT+EN (stima audit 118 era approssimativa: 57 da SPRINT.md + 79 da audit = 136 reali). AppState.language property + language_changed signal. Boot QSettings persistence in gui/app.py. Test sanità e quality gate Qt: OK.
- 2026-05-14: Audit completo startup app — tutti i bug documentati in CLAUDE.md risultano già risolti nel codice corrente. Nessun problema attivo allo startup (verifica statica).
- 2026-05-14: Verificato che pydantic_settings ha `extra="ignore"` solo sulla Config principale (riga 313-316). Le sub-config non ce l'hanno, ma funziona perché ogni sub usa `env_prefix` specifico.
- 2026-05-14: Creato `gui/state/app_state.py` (AppState singleton, 11 properties con guard, bridge `connect_signal_bus`). `_on_engine_status` aggancia anche `open_positions` e `mode` da `EngineStatusEvent` (campi presenti nel dataclass).
- 2026-05-14: Riscritto `gui/main_window.py` da 372→121 LOC. Layout: TopBar(42px)+QStackedWidget con DashboardWorkspace. Rimossi 9 QDockWidget, LogPanel interno, tutti i panel non usati (chart, watchlist, data, ai, engine, positions, backtest, pattern, broker). Aggiunti F1/Ctrl+K/F11 shortcut e bridge connect_signal_bus in __init__.
- 2026-05-15: Registrato gui/assets/icon.png come window icon in gui/app.py — gia' presente (Path(__file__).parent / "assets" / "icon.png" con guard exists()), nessuna modifica necessaria.
- 2026-05-14: Fix `QShortcut` import — in PyQt6 sta in `QtGui` non `QtWidgets`. App falliva subito allo startup.

## Lezioni apprese (permanenti)

- **i18n workspace names**: il nome nel dizionario `_WORKSPACE_DEFS` (es. `"order_ticket"`) deve avere una chiave `workspace.<name>` corrispondente in strings.py. Usare nomi divergenti (es. `workspace.order` vs `_WORKSPACE_NAMES[1]="order_ticket"`) causa fallback alla chiave grezza nella statusbar. Aggiungere sempre l'alias esatto.

- **Conteggio chiavi i18n**: la stima "50+68=118" nell'audit era approssimativa. Conteggio reale delle righe tabella: 57 (SPRINT.md) + 79 (audit nuove) = 136. Aggiornare il test assert con il valore reale, non la stima del documento.
- **Encoding UTF-8 su Windows**: `ast.parse(open(file).read())` fallisce su file con emoji/caratteri speciali (▶ ⏸ ● ○ …) perché PowerShell usa cp1252. Usare sempre `open(file, encoding='utf-8')` nei check sintattico su Windows.
- **PyQt6 compatibility (regole non derogabili):**
  - `QShortcut` sta in `PyQt6.QtGui`, NON `PyQt6.QtWidgets` (al contrario di PyQt5)
  - `QAction` sta in `PyQt6.QtGui`, NON `PyQt6.QtWidgets`
  - `contentsMargins` in `.ui` NON supporta né `<rect>` né `<margins>` → rimuovere dal `.ui` e impostare via `layout.setContentsMargins(l,t,r,b)` dopo `loadUi()`
  - `GraphicsLayoutWidget(background="#color")` non accettato → usare `gw = pg.GraphicsLayoutWidget(); gw.setBackground("#color")`
  - `pydantic_settings.Settings` legge tutto il `.env` → aggiungere `extra = "ignore"` al `class Config` per ignorare variabili di sub-settings
- **Qt6 font warning:** `tickFont` via `setStyle` genera warning `pointSize=-1` su Qt6 → non impostarlo, lascia default
- **Virtual env:** sempre usare `.venv312/Scripts/python.exe`, mai il Python 3.14 di sistema (torch DLL rotto)
- **AsyncIO + Qt:** GUI e Engine condividono stesso event loop via `qasync` — niente threading

## Pattern di codice scoperti

- `SignalBus` (`core/signal_bus.py`) come ponte unico asyncio→Qt: tutti i panel si abbonano qui
- File `.ui` caricati con `uic.loadUi(str(_UI), self)` dove `_UI = Path(__file__).parent.parent / "ui" / "<name>.ui"`
- Pattern panel custom (senza .ui) per layout complessi: BacktestPanel, AIAnalysisPanel hanno contenuto scrollabile costruito in Python

## Task aperti

- [x] Implementare nuova struttura `gui/main_window.py` con QStackedWidget + ActivityBar (vedi piano)
- [x] Creare `gui/state/app_state.py` come singleton stato globale
- [x] Creare `gui/i18n/` con 136 chiavi IT+EN, AppState.language + boot QSettings (Fase 1.6.2)
- [x] SettingsWorkspace + integrazione 6 workspace in main_window.py con Ctrl+1..6 (Fase 2)
- [x] Fase A.1 — filo conduttore: click watchlist→AppState, listener su AIPanel/ChartPanel/TopBar/OrderTicket, nuovo segnale current_scan_symbol
- [ ] Fix stati pulsanti positions/broker collegandoli a `AppState`
- [ ] DockArea drag-and-drop con pyqtgraph (oggi: workspace switching invece di dock)

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/paky.md` (spec personalità)
2. Identifica task aperti pertinenti al lavoro corrente

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai scoperto un'insidia non documentata
3. Aggiungi a "Pattern di codice scoperti" se hai identificato una convenzione riutilizzabile
4. Aggiorna "Task aperti"
