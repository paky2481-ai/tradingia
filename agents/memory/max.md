# Max — Memoria operativa

> File aggiornato dall'agente Max stesso al termine di ogni task.
> Max legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Avviato refactor radicale GUI + sistema agenti. Piano completo in `/root/.claude/plans/la-gui-pessima-delegated-bentley.md`.
- 2026-05-14: Accettata sfida utente "GUI perfetta o mobile". Definiti criteri di accettazione misurabili + gate review dopo fase 3.
- 2026-05-14: Decisi modelli agenti — Max=opus, Paky/Tom/Chloe/Marco=sonnet.
- 2026-05-14: GUI Fase 1 completata (PR #11, #12 mergiati). Demo TopBar + DashboardWorkspace + 5 info widget MVP + dark.qss 1203 LOC.
- 2026-05-14: Bug fix QShortcut (PR #13 mergiato) — `QShortcut` sta in `PyQt6.QtGui`, NON `QtWidgets`. Aggiunto quality gate non derogabile agli agent Paky/Marco: real import test + istanziazione widget prima di chiudere ogni task GUI.
- 2026-05-14: **Gate review SUPERATO** — utente ha lanciato l'app, conferma "così mi piace". Qt vince, Path B mobile non attivato. Procedere con Fase 1.5 Polish (3 ondate) poi Fasi 2-6.
- 2026-05-14: Difetti gate review documentati in `docs/SPRINT.md` (15 difetti, 3 ondate). Punto di ripartenza per nuova sessione: Fase 1.5 Ondata 1 (Marco).
- 2026-05-14: Aggiunto requisito utente i18n — IT default + EN opzionale, lasciare in inglese solo nomi tecnici riconosciuti (AI, ML, Hurst, Kelly, ATR, long/short, watchlist, broker, ecc.). Tabella di mapping completa con ~50 chiavi + tooltip esplicativi in `docs/SPRINT.md` Fase 1.6. Architettura: dict Python puro (no gettext/Qt Linguist), `gui/i18n/strings.py` con `tr()`, persistenza in QSettings, selettore in SettingsWorkspace.
- 2026-05-15: **Fase 1.5 COMPLETATA** — commit `f92bda2` consolida 15 fix gate review (Ondate 1+2+3): layout TopBar+WATCHLIST, header colonne posizioni, _GaugeCard border, regime/hurst da AppState (no divergenze), _AIPanel restyled con hit/miss sparkline, KPIBadge tooltip anchor, icon.png 256x256 candela verde, BrokerPill bullet U+2022. Quality gate import OK. Path venv su questo Windows: `.\.venv312\Scripts\python.exe` (NON `.venv`). Classe MainWindow è `TradingMainWindow` (non `MainWindow`).
- 2026-05-15: Avviata Fase 1.6.1 — audit testi UI hardcoded delegato a Marco. Visual check Fase 1.5 demandato all'utente al prossimo lancio app (non bloccante per audit read-only).

## Lezioni apprese (permanenti)

- L'utente vuole densità informativa Bloomberg-grade, non solo styling. Le statusbar oggi mostrano "Pronto" e nascondono tutto ciò che il motore calcola — questo è il problema reale da risolvere.
- Quando dai consigli strategici, includi sempre il trade-off principale in 1 riga prima di proporre l'opzione consigliata.
- L'utente apprezza le AskUserQuestion con opzione "Recommended" chiara — non galleggiare, prendi posizione.

## Consigli dati all'utente

- 2026-05-14: Consigliato Path A (Qt + qdarkstyle + info widgets ricchi) come opzione a basso rischio se TradingIA è uso personale. Path B (Flutter+FastAPI) raccomandato solo se il target è prodotto distribuibile.

## Task aperti

- [x] **Fase 1.5 — Polish difetti gate review** — completata 2026-05-15 (commit f92bda2)
- [ ] **Fase 1.6 — Internazionalizzazione (IT default + EN opzionale)** ← IN CORSO 2026-05-15
  - Step 1: audit testi UI hardcoded (Marco)
  - Step 2: crea `gui/i18n/` con dict IT/EN + AppState.language + QSettings persistence (Paky)
  - Step 3: sostituzione progressiva con `tr()` in TopBar → Dashboard → main_window → panel (Marco)
  - Step 4: test bilingue + selettore in SettingsWorkspace
- [ ] Fase 2 — 5 workspaces rimanenti (order_ticket, analysis, backtest, patterns, settings) **devono usare `tr()` da subito**
- [ ] Fase 3 — ActivityBar verticale + persistenza workspace in QSettings
- [ ] Fase 4 — 8 info widget rimanenti (ConfidenceBar, BiDirectionalBar, Heatmap, PingIndicator, StatusDot, LiveLabel, FFTMini, NumericTable)
- [ ] Fase 5 — Arricchimento panel atomici + 5 nuovi segnali SignalBus (Tom emit + Paky wire + Marco render)
- [ ] Fase 6 — Fix stati pulsanti via AppState in tutti i panel
- [ ] Validazione statistica pattern recognition (Tom + Chloe) — task strategico pre-esistente, da rivalutare dopo refactor GUI completo

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + CLAUDE.md
2. Identifica task aperti rilevanti
3. Saluta l'utente con "[Max]" e proponi continuità sui task aperti

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" solo se hai scoperto un'insidia non documentata
3. Aggiorna "Task aperti" (sposta a "Decisioni recenti" se completati)
