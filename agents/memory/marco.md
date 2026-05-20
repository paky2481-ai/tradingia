# Marco — Memoria operativa

> File aggiornato dall'agente Marco stesso al termine di ogni task.
> Marco legge questo file all'inizio di ogni sessione per recuperare contesto.
> Lo storico dettagliato delle fasi sta in `docs/SPRINT.md` — qui solo il recente + lezioni permanenti.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14→16: **Fasi 1→5 GUI completate** (storico in `docs/SPRINT.md`): libreria `gui/widgets/info/` (13 widget atomici), `dark.qss` 1203 LOC Bloomberg-grade, TopBar 42px, DashboardWorkspace, 4 workspace, ActivityBar 56px, refactor `tr()` su tutti i panel, arricchimento panel con listener SignalBus.
- 2026-05-18: **Cruscotto refactor** — da V-split illeggibile a chart sempre visibile + 2 macro-tab (Trading=Positions+Engine, Analisi=AI+Portfolio). Positions+Engine spostati in workspace Operativo. `_ChartArea` + `_GaugeStrip` separati. HelpIcon su 6 panel via `insertWidget`/`findChildren` (no modifica .ui).
- 2026-05-18: **Fix 4 bug Workspace Operativo** — `_field_label` minHeight, `metricsFrame` QSS scoped `#metricsFrame`, rimosso form manuale duplicato da PositionsPanel, `_symbol_combo` editable con sync bidirezionale anti-loop (`blockSignals`).
- 2026-05-20: **Fase C** — `_ChartArea` placeholder → `ChartPanel` reale in DashboardWorkspace, fetch async (pattern `_FundamentalsStrip`).
- 2026-05-20: **Selettore TF + periodo** — `ChartPanel` reso autonomo nel fetch. Striscia 28px con 2 `_SegmentedBar` (toggle esclusivo, QSS property `active`). Mapping periodo→limit, MAX→0. Rimosso fetch da DashboardWorkspace.
- 2026-05-20: **Fix date weekly + decimali** — `_DATE_ONLY_TF = {1d,1w,1wk,1mo}` in load_data; `PriceAxisItem` con `tickStrings` `.3f` fissi su left+right; decimali uniformati a millesimi su crosshair/tooltip/info bar; fix `VolumeItem._data=None` in `__init__`.
- 2026-05-20: **Asse X adattivo** — `TimeAxisItem` riscritto: `_timestamps` ora `list[pd.Timestamp]`, `set_timeframe()` calcola `bar_seconds`, `tickStrings()` usa `arc_seconds=spacing*bar_seconds` per scegliere il formato con contesto gerarchico ai confini. Retrocompat `list[str]` conservata.
- 2026-05-20: **Smoke test + screenshot benchmark** — App avviata offscreen, 0 crash, 0 errori. 6 screenshot in `screenshots/benchmark-2026-05-20/`. Fase B OK (_ScanChip nascosto), Fase D OK (StatusDot presente), Fase E OK (data_panel rimosso). Nessun difetto reale rilevato; rendering font offscreen (box) è artefatto ambientale, non bug.

## Lezioni apprese (permanenti)

- **TimeAxisItem adattivo:** pyqtgraph passa `spacing` in unità-barra a `tickStrings()`. `spacing*bar_seconds` = arco temporale tra due tick → unico discriminante del formato. Soglie: >=365g annuale, >=25g mensile, >=20h giornaliero, <20h intraday.
- **pyqtgraph rendering:** `QPicture` caching per candlestick; aggiornare solo l'ultima barra su tick live, non full redraw. Pen sempre cosmetico `width=0` (in QPicture il pen scala con la trasformazione → forex esplode). Wick degenere (`high==low`) = `drawLine` da un punto a se stesso che esplode: disegnare solo se `h>l`.
- **`setAutoVisible(y=True)`:** asse Y si adatta alle sole candele visibili — essenziale per zoom corretto.
- **PyQt6 QSS:** `QGraphicsItem` (pyqtgraph) NON stilabile via QSS — theming via `pg.setConfigOptions`/`setBackground()`. `QFrame{border:none}` globale NON sovrascrive stili inline (specificità inline > QSS); per bordi garantiti usare QFrame figlio con stylesheet diretta.
- **Densità Bloomberg:** micro-padding 4-8px (non 8-16 Material). 8 colori semantici bastano. Font numerico monospace tabulare. Animazioni mai > 200ms (flash tick 100ms).

## Pattern di rendering scoperti

- **Sparkline:** `QPicture` + `QPainter.drawPolyline()` su widget 80x24 → < 0.1ms.
- **Gauge orizzontale:** `drawRect()` + zone colorate + marker triangolare.
- **LiveLabel flash:** `QPropertyAnimation` su `palette()` color 100ms easing OutQuad.
- **NumericTable:** `QTableWidget` + `QStyledItemDelegate` per color coding cell-level senza setStyleSheet.
- **_SegmentedBar:** barra di pulsanti toggle esclusivo con QSS property `active` + `unpolish/polish` per refresh.

## Task aperti

- [x] Smoke test + screenshot benchmark sprint GUI (2026-05-20) — CHIUSO
- [ ] Osservatorio AI: area destra (ChartPanel) mostra empty-state perché nessun simbolo caricato a freddo — comportamento atteso ma da verificare su desktop reale con simbolo pre-selezionato

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/marco.md` (spec personalità)

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai scoperto una limitazione/feature non documentata di Qt/pyqtgraph
3. Aggiungi a "Pattern di rendering scoperti" se hai trovato una tecnica riutilizzabile
4. Aggiorna "Task aperti"
