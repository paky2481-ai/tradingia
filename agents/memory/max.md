# Max — Memoria operativa

> File aggiornato dall'agente Max stesso al termine di ogni task.
> Max legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Avviato refactor radicale GUI + sistema agenti. Piano completo in `/root/.claude/plans/la-gui-pessima-delegated-bentley.md`.
- 2026-05-14: Accettata sfida utente "GUI perfetta o mobile". Definiti criteri di accettazione misurabili + gate review dopo fase 3.
- 2026-05-14: Decisi modelli agenti — Max=opus, Paky/Tom/Chloe/Marco=sonnet.

## Lezioni apprese (permanenti)

- L'utente vuole densità informativa Bloomberg-grade, non solo styling. Le statusbar oggi mostrano "Pronto" e nascondono tutto ciò che il motore calcola — questo è il problema reale da risolvere.
- Quando dai consigli strategici, includi sempre il trade-off principale in 1 riga prima di proporre l'opzione consigliata.
- L'utente apprezza le AskUserQuestion con opzione "Recommended" chiara — non galleggiare, prendi posizione.

## Consigli dati all'utente

- 2026-05-14: Consigliato Path A (Qt + qdarkstyle + info widgets ricchi) come opzione a basso rischio se TradingIA è uso personale. Path B (Flutter+FastAPI) raccomandato solo se il target è prodotto distribuibile.

## Task aperti

- [ ] Esecuzione piano refactor GUI fase per fase
- [ ] Gate review dopo fase 3 (decisione Qt vs mobile)
- [ ] Validazione statistica pattern recognition (Tom + Chloe)

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + CLAUDE.md
2. Identifica task aperti rilevanti
3. Saluta l'utente con "[Max]" e proponi continuità sui task aperti

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" solo se hai scoperto un'insidia non documentata
3. Aggiorna "Task aperti" (sposta a "Decisioni recenti" se completati)
