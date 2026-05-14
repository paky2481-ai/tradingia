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

## Lezioni apprese (permanenti)

- L'utente vuole densità informativa Bloomberg-grade, non solo styling. Le statusbar oggi mostrano "Pronto" e nascondono tutto ciò che il motore calcola — questo è il problema reale da risolvere.
- Quando dai consigli strategici, includi sempre il trade-off principale in 1 riga prima di proporre l'opzione consigliata.
- L'utente apprezza le AskUserQuestion con opzione "Recommended" chiara — non galleggiare, prendi posizione.

## Consigli dati all'utente

- 2026-05-14: Consigliato Path A (Qt + qdarkstyle + info widgets ricchi) come opzione a basso rischio se TradingIA è uso personale. Path B (Flutter+FastAPI) raccomandato solo se il target è prodotto distribuibile.

## Task aperti

- [ ] **Fase 1.5 — Polish difetti gate review** (vedi `docs/SPRINT.md`):
  - Ondata 1: layout fixes (Marco, ~30 min)
  - Ondata 2: AI Panel destro restyling (Marco, ~45 min)
  - Ondata 3: polish finale tooltip/icon/centering (Paky+Marco, ~30 min)
- [ ] Fase 2 — 5 workspaces rimanenti (order_ticket, analysis, backtest, patterns, settings)
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
