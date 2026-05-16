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
- 2026-05-16: **Fase 1.6.2 + 1.6.3 COMPLETATE**. Commit `97e40d9` (Paky) crea `gui/i18n/strings.py` con dict IT/EN da 136 chiavi, funzione `tr()` con fallback alla chiave e interpolazione `.format()`, bootstrap QSettings in `gui/app.py`, setter `AppState.language` con segnale `language_changed`. Commit `2357c01` (Marco) refactor `tr()` nei 4 file GUI principali. Commit `b8239b8` (Marco) refactor `tr()` sui 8 panel atomici (~39 sostituzioni) — nessuna chiave nuova necessaria, già pre-create da Paky. Quality gate cross-validato (Marco+Max indipendenti): import test 8/8, istanziazione headless, test cambio lingua IT->EN runtime su BrokerPanel ("Salva impostazioni" -> "Save settings"). **Fase 1.6 Step 3 chiuso al 100%.** Resta solo Step 4 (selettore lingua in SettingsWorkspace) → fatto in Fase 2.
- 2026-05-16: **Fase 2 COMPLETATA** — commit `810387a`. 5 nuovi workspace creati in parallelo Marco+Paky (1285 LOC totali): `OrderTicketWorkspace` (QSplitter 3 col: form ordini + tabella + BrokerPanel), `AnalysisWorkspace` (QSplitter nested V/H: AI+Chart+Data), `BacktestWorkspace` (full-width BacktestPanel), `PatternsWorkspace` (Pattern+Chart H-split), `SettingsWorkspace` (QScrollArea con 4 sezioni: lingua/broker/risk/info). `main_window.py` esteso (121→185 LOC) con 6-workspace QStackedWidget + Ctrl+1..6 shortcut + persistenza QSettings (workspace attivo + window_geometry) + statusbar tradotta. **Step 4 di Fase 1.6 chiuso**: selettore lingua IT/EN in SettingsWorkspace salva in QSettings + applica AppState.language + dialog "Riavvia per applicare". 187 chiavi i18n totali (50 nuove tra Marco e Paky), copertura IT=EN al 100%. Decisione architetturale: ogni workspace istanzia autonomamente i panel atomici (no shared singleton) — semplice e robusto, sync dati via SignalBus/AppState.
- 2026-05-16: Lezione delega parallela — Marco e Paky possono lavorare su `gui/i18n/strings.py` simultaneamente SE leggono il file prima di scrivere e usano nomi chiave non sovrapposti. Pattern `_try_import_workspace()` graceful in `main_window.py` permette dev parallelo senza ImportError al boot.
- 2026-05-16: Lezione encoding — su PowerShell Windows serve sempre `$env:PYTHONIOENCODING="utf-8"` per stampare caratteri Unicode (▶, ⏸, →, ·, ecc.) in stdout dai test Python. Senza, errore `UnicodeEncodeError: 'charmap' codec`. Documentato per evitare falsi negativi nei quality gate.

## Lezioni apprese (permanenti)

- L'utente vuole densità informativa Bloomberg-grade, non solo styling. Le statusbar oggi mostrano "Pronto" e nascondono tutto ciò che il motore calcola — questo è il problema reale da risolvere.
- Quando dai consigli strategici, includi sempre il trade-off principale in 1 riga prima di proporre l'opzione consigliata.
- L'utente apprezza le AskUserQuestion con opzione "Recommended" chiara — non galleggiare, prendi posizione.

## Consigli dati all'utente

- 2026-05-14: Consigliato Path A (Qt + qdarkstyle + info widgets ricchi) come opzione a basso rischio se TradingIA è uso personale. Path B (Flutter+FastAPI) raccomandato solo se il target è prodotto distribuibile.

## Task aperti

- [x] **Fase 1.5 — Polish difetti gate review** — completata 2026-05-15 (commit f92bda2)
- [x] **Fase 1.6 — Internazionalizzazione (IT default + EN opzionale)** — completata 2026-05-16 (Step 1-4 al 100%, commit `97e40d9`, `2357c01`, `b8239b8`, `810387a` per Step 4)
- [x] **Fase 2 — 5 workspaces rimanenti** — completata 2026-05-16 (commit `810387a`)
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
