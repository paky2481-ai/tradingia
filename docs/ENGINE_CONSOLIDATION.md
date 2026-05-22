# Piano di Consolidamento Engine — TradingIA

> Redatto da Paky — 2026-05-21. Da rivedere con Max prima di esecuzione.
> Questo documento NON autorizza modifiche al motore di paper trading.

---

## Contesto: i due engine

| Classe | File | Ruolo attuale |
|--------|------|---------------|
| `TradingEngine` | `core/engine.py` | Engine operativo attivo: paper trading live, loop 1h/4h, posizioni, P&L |
| `TradingOrchestrator` | `core/orchestrator.py` | Coordinatore avanzato: integra StrategyManager, AutoConfig, SignalBus; usato come wrapper dal main |

Entrambi co-esistono. L'Orchestrator *chiama* l'Engine internamente. Il problema:

1. **Duplicazione di responsabilità**: il loop di scan vive nell'Engine *e* nell'Orchestrator con logiche parzialmente sovrapposte.
2. **Due percorsi verso StrategyManager**: l'Engine chiama direttamente `strategy_manager.evaluate()`; l'Orchestrator ha la propria pipeline AI.
3. **SignalBus non uniforme**: l'Engine emette eventi SignalBus direttamente; l'Orchestrator ha un layer intermedio. Risultato: alcune GUI ricevono eventi doppi o in ordine non deterministico.
4. **AppState disaccoppiato dall'Engine**: `AppState.engine_running` è sincronizzato via SignalBus, ma l'Engine non conosce AppState — se il bus fallisce, lo stato GUI diverge dallo stato reale.

---

## Rischi identificati (dall'audit S0)

| # | Rischio | Gravità |
|---|---------|---------|
| R1 | Fusione prematura rompe paper trading vivo | CRITICO |
| R2 | I loop async di Engine hanno riferimenti circolari con Orchestrator | ALTO |
| R3 | Il Backtester usa `BaseStrategy.generate_signals()` direttamente — non può cambiare contratto | MEDIO |
| R4 | La GUI dipende da `EngineStatusEvent` emesso dall'Engine — se viene migrato, i panel si rompono | MEDIO |

---

## Piano in due tempi

### Fase 1 — Adapter (NON rompe il paper trading, eseguibile con flag)

**Obiettivo**: creare una classe `EngineAdapter` che espone l'interfaccia dell'Engine verso
l'Orchestrator tramite un contratto esplicito (interfaccia ABC), senza spostare nessuna logica.

**Passi concreti:**

1. Definire `core/engine_interface.py` con ABC `AbstractEngine`:
   - `async start()`, `async stop()`
   - `is_running() -> bool`
   - `get_equity() -> float`
   - `get_positions() -> List[Position]`
   - `get_daily_pnl() -> float`

2. Far implementare questa ABC a `TradingEngine` (retrocompatibile — solo aggiunta `ABCMeta`).

3. Creare `core/engine_adapter.py` come thin wrapper che:
   - accetta una istanza `AbstractEngine` (default: `TradingEngine`)
   - espone la stessa API verso l'Orchestrator
   - centralizza tutti gli `emit_*` del SignalBus (rimuove le emit sparse nell'Engine)

4. `TradingOrchestrator.__init__` accetta `engine: AbstractEngine = None` — se None crea `TradingEngine`.

**Punti di rottura da verificare:**
- `core/orchestrator.py` riga ~140: `self.engine.start()` — deve funzionare via adapter
- `gui/panels/engine_panel.py`: legge `AppState.engine_running` — non tocca l'Engine direttamente, OK
- `core/signal_bus.py`: `emit_engine_status` è chiamato dall'Engine loop — dopo l'adapter verrà centralizzato qui

**Gate di validazione Fase 1:**
- Paper trading gira invariato con adapter interposto (stesso comportamento osservabile via GUI)
- Nessun cambiamento all'API pubblica di Orchestrator verso `main.py`

---

### Fase 2 — Migrazione (solo dopo che Fase 1 è stabile in paper trading)

**Obiettivo**: `TradingOrchestrator` diventa l'unico engine collegato a GUI e SignalBus.
`TradingEngine` viene convertito in un `ExecutionBackend` puro (ordini, posizioni, P&L)
senza loop di scan.

**Passi concreti:**

1. Spostare il loop di scan (1h/4h) dall'Engine all'Orchestrator con un `ScanLoop` dedicato.

2. `TradingEngine` diventa `ExecutionBackend`:
   - gestisce solo ordini, posizioni, stop loss
   - non emette più `scan_result` né `engine_status` (li emette l'Orchestrator)

3. `AppState.engine_running` viene aggiornato direttamente dall'Orchestrator (non via Bus roundtrip).

4. `StrategyManager.signal_registry` viene esposto all'Orchestrator per inject dei segnali S2
   nel loop di scan.

**Punti di rottura da verificare prima di eseguire:**
- Tutti i test di fumo GUI (TopBar engine indicator, EnginePanel, ScanChip)
- `backtesting/backtester.py` — non usa l'Engine, usa solo `BaseStrategy` — invariato
- `main.py` — usa solo `Orchestrator.start()` — invariato se Fase 1 completa
- `database/trade_store.py` — aggiornato dall'Engine via await — verificare che
  `ExecutionBackend` mantenga questo flusso

**Gate di validazione Fase 2:**
- Walk-forward backtest identico prima e dopo la migrazione (nessuna regressione)
- Paper trading 24h continuo senza crash
- Tutti i smoke test GUI (cfr. `docs/SPRINT.md`) passano

---

## Dipendenze e ordine di esecuzione

```
S2 (registry) — questo task, COMPLETATO
     ↓
Fase 1 Adapter — Max approva questo doc, Paky esegue
     ↓  (paper trading invariato)
Segnali S2 testati in paper trading
     ↓
Fase 2 Migrazione — solo dopo paper trading stabile
```

---

## Note operative

- **Non eseguire Fase 1 durante sessioni di paper trading attive** (fermare l'engine prima).
- Il branch di sviluppo per Fase 1 sarà `feat/engine-adapter` — NON mergeable su main senza
  review di Max + smoke test completo.
- Se Fase 1 rivela problemi imprevisti nell'adapter, il fallback è mantenere lo status quo
  (Orchestrator + Engine come oggi) a tempo indeterminato — il sistema funziona.
