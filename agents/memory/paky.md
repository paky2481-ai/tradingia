# Paky — Memoria operativa

> File aggiornato dall'agente Paky stesso al termine di ogni task.
> Paky legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Audit completo startup app — tutti i bug documentati in CLAUDE.md risultano già risolti nel codice corrente. Nessun problema attivo allo startup (verifica statica).
- 2026-05-14: Verificato che pydantic_settings ha `extra="ignore"` solo sulla Config principale (riga 313-316). Le sub-config non ce l'hanno, ma funziona perché ogni sub usa `env_prefix` specifico.
- 2026-05-14: Creato `gui/state/app_state.py` (AppState singleton, 11 properties con guard, bridge `connect_signal_bus`). `_on_engine_status` aggancia anche `open_positions` e `mode` da `EngineStatusEvent` (campi presenti nel dataclass).
- 2026-05-14: Riscritto `gui/main_window.py` da 372→121 LOC. Layout: TopBar(42px)+QStackedWidget con DashboardWorkspace. Rimossi 9 QDockWidget, LogPanel interno, tutti i panel non usati (chart, watchlist, data, ai, engine, positions, backtest, pattern, broker). Aggiunti F1/Ctrl+K/F11 shortcut e bridge connect_signal_bus in __init__.

## Lezioni apprese (permanenti)

- **PyQt6 uic compatibility:**
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
