# Paky — Memoria operativa

> File aggiornato dall'agente Paky stesso al termine di ogni task.
> Paky legge questo file all'inizio di ogni sessione per recuperare contesto.
> Lo storico dettagliato delle fasi sta in `docs/SPRINT.md` — qui solo il recente + lezioni permanenti.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Riscritto `gui/main_window.py` (372→121 LOC): TopBar + QStackedWidget, rimossi 9 QDockWidget. Creato `gui/state/app_state.py` (AppState singleton, properties con guard, bridge `connect_signal_bus`).
- 2026-05-15→16: **i18n + workspace + ActivityBar** (storico in `docs/SPRINT.md`): `gui/i18n/` con 136 chiavi IT+EN, `AppState.language` + persistenza QSettings; SettingsWorkspace + 6 workspace in main_window con Ctrl+1..6; ActivityBar integrata (layout root QHBoxLayout, fallback graceful).
- 2026-05-16: **Fase 5.1** — emit dei 5 segnali SignalBus nei moduli core (engine loop heartbeat, orchestrator ai_result, risk_manager kelly_update, auto_config regime_update, engine correlation_update).
- 2026-05-18: **Fase A.1 — filo conduttore**: WatchlistPanel click → `AppState.current_symbol`; nuovo segnale `current_scan_symbol(str,str)` + emit nei loop engine; AIAnalysisPanel/ChartPanel ascoltano `current_symbol_changed`; OrderTicket QComboBox con sync bidirezionale; chip simbolo TopBar.
- 2026-05-20: **Fase 6 — stati pulsanti via AppState**: submit ordine engine-gated, EnginePanel refactor su `AppState.engine_running` (fonte unica, sync con TopBar), loading state Test broker, Clear pattern condizionale. (Task interrotto da ECONNRESET, completato e validato da Max — commit `3449306`.)

## Lezioni apprese (permanenti)

- **i18n workspace names**: il nome in `_WORKSPACE_DEFS` deve avere chiave `workspace.<name>` esatta in strings.py, altrimenti fallback alla chiave grezza nella statusbar.
- **Encoding UTF-8 Windows**: `ast.parse(open(file).read())` fallisce su file con caratteri speciali (▶ ⏸ ● …) perché PowerShell usa cp1252. Usare sempre `open(file, encoding='utf-8')`.
- **PyQt6 (regole non derogabili):**
  - `QShortcut` e `QAction` stanno in `PyQt6.QtGui`, NON `QtWidgets` (al contrario di PyQt5)
  - `contentsMargins` nei `.ui` → rimuovere il blocco `<property>`; impostare margini solo dove il layout è creato in Python, non dopo `loadUi`
  - `GraphicsLayoutWidget(background=...)` non accettato → `gw = pg.GraphicsLayoutWidget(); gw.setBackground(...)`
  - `pydantic_settings`: `extra = "ignore"` nel `class Config` per ignorare variabili di sub-settings
  - `tickFont` via `setStyle` genera warning `pointSize=-1` su Qt6 → non impostarlo
- **Virtual env:** sempre `.venv312/Scripts/python.exe`, mai il Python 3.14 di sistema (torch DLL rotto).
- **AsyncIO + Qt:** GUI ed Engine condividono lo stesso event loop via `qasync` — niente threading.

## Pattern di codice scoperti

- `SignalBus` (`core/signal_bus.py`) ponte unico asyncio→Qt: tutti i panel si abbonano qui.
- File `.ui` caricati con `uic.loadUi(str(_UI), self)` dove `_UI = Path(__file__).parent.parent / "ui" / "<name>.ui"`.
- Panel custom senza `.ui` (BacktestPanel, AIAnalysisPanel, BrokerPanel) per layout complessi costruiti in Python.
- Fetch async dalla GUI: `loop = asyncio.get_event_loop(); if loop.is_running(): asyncio.ensure_future(...)` in try/except per headless.

## Task aperti

- [ ] DockArea drag-and-drop con pyqtgraph (oggi: workspace switching invece di dock) — eventuale, non prioritario

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/paky.md` (spec personalità)
2. Identifica task aperti pertinenti al lavoro corrente

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai scoperto un'insidia non documentata
3. Aggiungi a "Pattern di codice scoperti" se hai identificato una convenzione riutilizzabile
4. Aggiorna "Task aperti"
