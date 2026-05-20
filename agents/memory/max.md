# Max — Memoria operativa

> File aggiornato dall'agente Max stesso al termine di ogni task.
> Max legge questo file all'inizio di ogni sessione per recuperare contesto.
> Lo storico dettagliato delle fasi sta in `docs/SPRINT.md` — qui solo il recente + le lezioni permanenti.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Avviato refactor radicale GUI Bloomberg-grade + sistema 5 agenti (Max=opus, Paky/Tom/Chloe/Marco=sonnet). **Gate review SUPERATO** ("così mi piace"): Qt vince, Path B mobile non attivato.
- 2026-05-14→16: **Fasi 1.5→5 completate** (storico dettagliato in `docs/SPRINT.md`): polish gate review, i18n IT/EN (dict Python puro, `tr()`, ~187 chiavi), 5 workspace + QStackedWidget Ctrl+1..6, ActivityBar verticale, 13 info widget atomici, 5 segnali SignalBus con pipeline live emit→listener.
- 2026-05-18: **Fase A — filo conduttore architetturale**. Visione utente: trader umano single-instrument (frontend) vs AI multi-instrument (backend) separati. `AppState.current_symbol` sorgente unica, segnale `current_scan_symbol`, chip simbolo TopBar. Cruscotto trader-puro, workspace Analisi → `AIObservatoryWorkspace`. Workspace Data eliminato (fundamentals come strip nel Cruscotto). Piano residuo: fasi B-C-D-E.
- 2026-05-18: **Fase 5.5/5.6/5.7** — Cruscotto refactor: chart sempre visibile + macro-tab, panel atomici reali al posto dei widget interni, HelpIcon su 6 panel. Fix 4 bug Workspace Operativo (commit `8595075`): layout form, caption EnginePanel, rimozione form manuale duplicato, sync simbolo custom end-to-end.
- 2026-05-20: **Fase C — chart integration** (commit `e43423d`). `_ChartArea` placeholder → `ChartPanel` reale (CandlestickChart pyqtgraph). Fetch OHLCV async su `current_symbol`.
- 2026-05-20: **Fix barra gigante chart** (commit `267e38f`). Candele forex con `high==low` → wick `drawLine` da un punto a se stesso che sotto la scala forex nel QPicture esplodeva a tutta altezza. Fix: wick solo se `h>l`. Diagnosi via screenshot headless iterativi.
- 2026-05-20: **Fase 6 — stati pulsanti via AppState** (commit `3449306`). Submit ordine engine-gated, EnginePanel su `AppState.engine_running` (sync con TopBar), loading state Test broker, Clear pattern condizionale. Lavoro di Paky interrotto da ECONNRESET, ripreso e validato da Max.
- 2026-05-20: **Selettore timeframe + quick-range** (commit `26f55cf`). Striscia con 2 `_SegmentedBar` (TF 1H/4H/1D/1W + periodo 3M/1A/5A/MAX). `ChartPanel` reso autonomo nel fetch (ascolta current_symbol + propri selettori), fetch rimosso da `DashboardWorkspace`. Default 1H+1A.
- 2026-05-20: **4 fix post visual check** (commit `9c75216` data + `5b06406` chart). (1) `sanitize_ohlcv()` in `data/feed.py`: clampa barre OHLCV corrotte (es. GBPUSD 2012 low=0.637) preservando i movimenti reali. (2) date asse X weekly. (3) `PriceAxisItem` decimali fissi. (4) resample `4H`→`4h`. Delega parallela Tom (data) + Marco (chart).
- 2026-05-20: **Asse X temporale adattivo** (commit `2c961de`). `TimeAxisItem` tiene `pd.Timestamp` reali, formatta dinamicamente in base allo zoom (anno/mese+anno/giorno+mese/ora) con contesto gerarchico ai confini.

## Lezioni apprese (permanenti)

- L'utente vuole densità informativa Bloomberg-grade, non solo styling. Mostrare ciò che il motore calcola, non nascondere dietro "Pronto".
- Quando dai consigli strategici, includi sempre il trade-off principale in 1 riga prima di proporre l'opzione consigliata.
- L'utente apprezza le AskUserQuestion con opzione "Recommended" chiara — non galleggiare, prendi posizione.
- **Encoding Windows trap**: PowerShell `Get-Content -Raw` legge in CP1252; salvare poi con `Set-Content -Encoding utf8` corrompe i byte multibyte UTF-8 (▶ € → · ✦) in mojibake. Per find&replace su file UTF-8 usare ESCLUSIVAMENTE Python (`Path.read_text/write_text(encoding="utf-8")`). Per stampare Unicode in stdout dai test: `$env:PYTHONIOENCODING="utf-8"`.
- **Commit message PowerShell**: il here-string `git commit -m @'...'@` in PS 5.1 spezza su `+ <-> && `. Workaround: `git commit -F file.txt` con messaggio in file UTF-8, oppure `-m` multipli senza caratteri operatore.
- **Diagnosi rendering**: quando più fix falliscono in fila, isolare la variabile con dati di test modificati (es. allargare le wick) discrimina la causa reale invece di tirare a indovinare.
- **pandas >= 2.2**: alias di frequenza maiuscoli (`H`, `T`, `S`) rimossi — usare minuscoli (`h`, `min`, `s`) in `resample()`.

## Consigli dati all'utente

- 2026-05-14: Path A (Qt + info widgets ricchi) consigliato per uso personale; Path B (Flutter+FastAPI) solo se il target è prodotto distribuibile. → Path A scelto.

## Task aperti

- [ ] **PUNTO DI RIPARTENZA**: scegliere prossima fase tra:
   - Fase E — Pulizia: fix Pattern recognition + unifica 2 watchlist + rimuovi data_panel
   - Fase B — Backend visibile polish: indicatore "engine sta scansionando X"
   - Fase D resto — auto-download al primo click simbolo non in cache
   - Bridge tick-live: collegare `ChartPanel.update_live_tick()` al SignalBus
   - Robustezza data feed: errori intermittenti `curl: (16)` (HTTP/2) + "possibly delisted" da yfinance — valutare retry/fallback HTTP/1.1
- [ ] Validazione statistica pattern recognition (Tom + Chloe) — task strategico, da rivalutare dopo refactor GUI

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + CLAUDE.md
2. Identifica task aperti rilevanti
3. Saluta l'utente con "[Max]" e proponi continuità sui task aperti

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" solo se hai scoperto un'insidia non documentata
3. Aggiorna "Task aperti" (sposta a "Decisioni recenti" se completati)
