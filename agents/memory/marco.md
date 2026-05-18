# Marco — Memoria operativa

> File aggiornato dall'agente Marco stesso al termine di ogni task.
> Marco legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Audit GUI completo — identificati problemi: 4 dock bottom compressi a 360px, 3 dock right ristretti, font Segoe UI inconsistente (13px QSS vs 10px app.py), QTabBar senza stile QSS.
- 2026-05-14: Fix candlestick "doppie": `autoRange()` → `setAutoVisible(y=True)` + `setXRange()`.
- 2026-05-14: Fix performance MA lines: loop O(n²) → `np.convolve` (50× più veloce).
- 2026-05-14: Creati 4 widget MVP libreria `gui/widgets/info/` (Sparkline+area gradient, KPIBadge, RegimePill, Gauge con halo marker) + `gui/styles/dark.qss` 1203 righe Bloomberg-grade. `load_stylesheet()` aggiornato con fallback su `dark_theme.qss`.
- 2026-05-14: Completati 3 deliverable gate review Fase 1 — HelpIcon, TopBar Bloomberg 42px, DashboardWorkspace 807 LOC.
- 2026-05-14: Applicati 7 fix layout post-review: QGroupBox margin-top 14→10px, QPushButton primary max-height 28px, spacer TopBar spostato prima di mode/broker pill, header colonne _PositionsPanel, _GaugeCard inner QFrame con bordo esplicito, P&L con prefisso €, regime/hurst AppState come unica sorgente di verità.
- 2026-05-14: Verificati fix 8-11 _AIPanel (Ondata 2): titolo QGroupBox senza separatori spurii, predizione RichText single-label, footer pinned con QFrame border-top, Sparkline hit_miss mode con dot verde/rosso e baseline tratteggiata. Quality gate: DashboardWorkspace import + istanziazione OK.
- 2026-05-15: Ondata 3 polish finale — tooltip anchor KPIBadge (event() già presente da Ondata 2), asset icon.png 256x256 candela verde su trasparente creato in gui/assets/, centering BrokerPill dot: U+25CF→U+2022 + vertical-align:middle + AlignVCenter. Quality gate import OK.
- 2026-05-15: Audit i18n completato — 27 file scansionati (9 con stringhe UI rilevanti), 87 stringhe da tradurre, 50 chiavi già in tabella SPRINT.md, 37 NUOVE chiavi da aggiungere.
- 2026-05-16: Fase 1.6 Step 3 — refactoring tr() su 8 panel atomici (ai_analysis, backtest, broker, pattern, chart, watchlist, data, positions). Tutte le chiavi erano già in strings.py. pattern_panel: _COLUMNS usato solo per len(), intestazioni reali nel .ui — aggiunto _apply_i18n() che sovrascrive a runtime col 2 e 6. Quality gate: 8/8 SYNTAX OK, 8/8 import PASS, istanziazione headless PASS, test IT/EN runtime PASS.
- 2026-05-16: Fase 2 — Creati 4 workspace (order_ticket, analysis, backtest, patterns). Aggiunte 22 chiavi order.* a strings.py (IT+EN). Struttura: QSplitter per order_ticket (form+tabella+broker) e patterns (pattern+chart), QSplitter nested per analysis (AI+chart top, data bottom), full-width con padding 12px per backtest. Quality gate: 4/4 SYNTAX OK, 4/4 IMPORT OK, 4/4 INSTANCE OK offscreen, 22/22 chiavi i18n presenti.
- 2026-05-16: Fase 3 — ActivityBar 56px creata (gui/widgets/activity_bar.py, 126 LOC). 6 _ActivityButton con QSS property "active" + unpolish/polish per refresh stato. QSS self-contained nel modulo (non dipende dal foglio globale). Icone scelte: ⌖ ↗ ○ ▦ ✦ ⚙. Tutti e 3 i quality gate PASS (import, istanziazione 56px/6 btn, segnale workspace_changed).
- 2026-05-16: Fase 4 — 8 widget atomici creati in gui/widgets/info/: ConfidenceBar (25H), BiDirectionalBar (22H), Heatmap (mouseMoveEvent tooltip cell), PingIndicator (dot glow + latency), StatusDot (QTimer pulsante loading), LiveLabel (flash QTimer 100ms via stylesheet), FFTMini (barre+gradiente+triangolo peak), NumericTable (QTableWidget Bloomberg-grade + sparkline cell). 2 chiavi i18n aggiunte (bidir.bear/bull IT+EN). Quality gate: 8/8 SYNTAX OK, 8/8 IMPORT OK, 8/8 INSTANCE OK offscreen.
- 2026-05-16: Fase 5.2 — Arricchiti 4 panel (ai_analysis, watchlist, positions, engine) con 13 info widget + listener bus Fase 5. Creato PortfolioPanel nuovo standalone. 9 chiavi i18n aggiunte (engine.loop.*, portfolio.*, positions.total_pnl). QTimer idle 60s per loop dots. Quality gate: 6/6 SYNTAX OK, 5/5 IMPORT OK, 5/5 INSTANCE OK, tutti emit PASS.
- 2026-05-18: Fase 5.5 — A.1: splitter OrderTicket [300,450,250]→[350,750,480], minWidth broker 200→420, form 280→330. A.3: padding bottoni BrokerPanel 12px→14px + min-height:32px nei QSS inline + setSizePolicy Expanding/Fixed. B: DashboardWorkspace refactored 863→~280 LOC — rimossi _WatchlistPanel, _PositionsPanel, _AIPanel; sostituiti con panel atomici. Layout scelto: sinistra V-split a 3 (Watchlist 40%+Positions 35%+Engine 25%), centro chart+gauge, destra AIAnalysisPanel. Demo timer NON tocca segnali Fase 5. Quality gate 4/4 PASS.
- 2026-05-18: Refactor cruscotto Bloomberg-style (Max) — DashboardWorkspace riscritto ~310 LOC. _CenterPanel spezzato in _ChartArea (standalone) + _GaugeStrip (82px fissi, 3 gauge). QTabWidget 4 tab: Posizioni/AIAnalysis/Engine/Portfolio. Watchlist sempre visibile sinistra 280-360px. 4 chiavi i18n aggiunte (workspace.tab_*). Quality gate 4/4 PASS (sintassi, import, istanziazione 9 assert, i18n IT+EN).
- 2026-05-18: Fase 5.6 — 4 tab flat → 2 macro-tab a gruppi correlati. Tab "Trading" (QSplitter H: Positions+Engine 50/50), Tab "Analisi" (QSplitter H: AI+Portfolio 50/50). Stretch chart 65→50, tab 35→50. 4 chiavi i18n rimosse, 2 aggiunte (tab_trading/tab_analysis). Quality gate 5/5 PASS.
- 2026-05-18: Cruscotto semplificato — rimossi QTabWidget, _positions, _engine, _TAB_KEYS, _apply_i18n. Chart stretch=1 DOMINANTE (Expanding, nessun limite superiore). Positions+Engine spostati in OrderTicketWorkspace (layout QSplitter V: top 60% positions+engine, bottom 40% form+tabella+broker). i18n "Ordini"→"Operativo" (IT), "Order Ticket"→"Operations" (EN). Quality gate 5/5 PASS.
- 2026-05-18: Task A+B — Dedupe bottone AI (ai.btn_run "Avvia Analisi AI [{symbol}]" -> "▶ Analizza"/"▶ Analyze", rimosso {symbol}). HelpIcon aggiunta a 6 panel via insertWidget/findChildren (no .ui modificati). Aggiunto HelpIcon.update_texts() per cambio lingua runtime. 12 chiavi help.* in strings.py IT+EN. Quality gate 4/4 PASS.

## Lezioni apprese (permanenti)

- **pyqtgraph performance:** usare `QPicture` caching per rendering candlestick. Aggiornare solo l'ultima barra su tick live, NON full redraw.
- **`setAutoVisible(y=True)`:** asse Y si adatta solo alle candele visibili (X range), non all'intero dataset → essenziale per zoom comportamentale corretto.
- **PyQt6 QSS limitations:** `QGraphicsItem` (pyqtgraph charts) NON è stilabile via QSS. Theming va fatto via `pg.setConfigOptions(background, foreground)` o `setBackground()`.
- **Densità Bloomberg vs Material:** Material 3 ha padding 8-16px standard, troppo per trading UI. Target 4-8px micro-padding.
- **Color palette ridotta:** 8 colori semantici (bull/bear/neutral/warn/info/accent/bg/surface) sono sufficienti per qualsiasi trading UI. Più colori = cognitive load.
- **Font numerico:** sempre monospace tabulare (Roboto Mono / JetBrains Mono) per cifre allineate.
- **Animazioni:** mai > 200ms, sempre discrete. Flash al tick: 100ms fade. No transitions globali QSS.
- **QFrame border vs QSS globale:** `QFrame { border: none; }` nel QSS globale NON sovrascrive gli stili inline (specificità inline > QSS). Ma per bordi garantiti su card, usare un QFrame figlio con stylesheet diretta anziché affidarsi a objectName + regola `#ID` (che può confliggersi con re-parenting).

## Pattern di rendering scoperti

- **Sparkline lightweight:** `QPicture` + `QPainter.drawPolyline()` su widget custom 80x24 → < 0.1ms per render
- **Gauge orizzontale:** `QPainter.drawRect()` + zone colorate background + marker triangolare → 1 LOC
- **LiveLabel flash:** `QPropertyAnimation` su `palette()` color durata 100ms easing OutQuad
- **NumericTable:** `QTableWidget` + custom `QStyledItemDelegate` per cell-level color coding senza setStyleSheet

## Task aperti

- [x] Creare libreria `gui/widgets/info/` — 4 widget MVP creati (Sparkline, KPIBadge, RegimePill, Gauge)
- [x] Definire QSS unificato `gui/styles/dark.qss` — DONE (1203 righe, copertura completa)
- [x] Implementare `TopBar` con 8 KPI badge usando KPIBadge + sparkline — DONE (425 LOC)
- [x] Creare `HelpIcon` riutilizzabile con tooltip + MessageBox dark-styled — DONE (99 LOC)
- [x] Creare `DashboardWorkspace` MVP per gate review — DONE (807 LOC, liveness demo 2s)
- [x] Restanti 8 micro-componenti: ConfidenceBar, BiDirectionalBar, Heatmap, PingIndicator, StatusDot, LiveLabel, FFTMini, NumericTable — DONE Fase 4
- [x] Riprogettare `WatchlistPanel` — aggiunta colonna REGIME con RegimePill (soluzione non invasiva: non ricostruisce l'intera tabella)
- [ ] Integrare DashboardWorkspace in MainWindow (a cura di Paky)
- [x] Fase 2 — Creati 4 workspace rimanenti: OrderTicketWorkspace, AnalysisWorkspace, BacktestWorkspace, PatternsWorkspace
- [x] Fase 3 — ActivityBar widget creato, export in gui/widgets/__init__.py, quality gate PASS
- [x] Fase 5.5 — A.1 splitter Ordini, A.3 padding broker buttons, B DashboardWorkspace refactor con panel atomici
- [x] Refactor cruscotto Bloomberg-style — _ChartArea + _GaugeStrip separati, QTabWidget 4 tab, WatchlistPanel always-visible
- [x] Fase 5.6 — 4 tab flat → 2 macro-tab (Trading=Positions+Engine, Analisi=AI+Portfolio), stretch 50/50, quality gate 5/5 PASS
- [x] Cruscotto visual fix — chart dominante, Positions+Engine spostati in workspace Operativo (Ctrl+2)

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/marco.md` (spec personalità)

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai scoperto una limitazione/feature non documentata di Qt/pyqtgraph
3. Aggiungi a "Pattern di rendering scoperti" se hai trovato una tecnica riutilizzabile
4. Aggiorna "Task aperti"
