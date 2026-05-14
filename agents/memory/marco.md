# Marco — Memoria operativa

> File aggiornato dall'agente Marco stesso al termine di ogni task.
> Marco legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Audit GUI completo — identificati problemi: 4 dock bottom compressi a 360px, 3 dock right ristretti, font Segoe UI inconsistente (13px QSS vs 10px app.py), QTabBar senza stile QSS.
- 2026-05-14: Fix candlestick "doppie": `autoRange()` → `setAutoVisible(y=True)` + `setXRange()`.
- 2026-05-14: Fix performance MA lines: loop O(n²) → `np.convolve` (50× più veloce).
- 2026-05-14: Creati 4 widget MVP libreria `gui/widgets/info/` (Sparkline+area gradient, KPIBadge, RegimePill, Gauge con halo marker) + `gui/styles/dark.qss` 1203 righe Bloomberg-grade. `load_stylesheet()` aggiornato con fallback su `dark_theme.qss`.
- 2026-05-14: Completati 3 deliverable gate review Fase 1 — HelpIcon (già presente dal task precedente), TopBar Bloomberg 42px (già presente), DashboardWorkspace 807 LOC con _WatchlistPanel, _PositionsPanel, _CenterPanel (3 Gauge cards), _AIPanel, QTimer demo liveness 2s.

## Lezioni apprese (permanenti)

- **pyqtgraph performance:** usare `QPicture` caching per rendering candlestick. Aggiornare solo l'ultima barra su tick live, NON full redraw.
- **`setAutoVisible(y=True)`:** asse Y si adatta solo alle candele visibili (X range), non all'intero dataset → essenziale per zoom comportamentale corretto.
- **PyQt6 QSS limitations:** `QGraphicsItem` (pyqtgraph charts) NON è stilabile via QSS. Theming va fatto via `pg.setConfigOptions(background, foreground)` o `setBackground()`.
- **Densità Bloomberg vs Material:** Material 3 ha padding 8-16px standard, troppo per trading UI. Target 4-8px micro-padding.
- **Color palette ridotta:** 8 colori semantici (bull/bear/neutral/warn/info/accent/bg/surface) sono sufficienti per qualsiasi trading UI. Più colori = cognitive load.
- **Font numerico:** sempre monospace tabulare (Roboto Mono / JetBrains Mono) per cifre allineate.
- **Animazioni:** mai > 200ms, sempre discrete. Flash al tick: 100ms fade. No transitions globali QSS.

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
- [ ] Restanti 8 micro-componenti: ConfidenceBar, BiDirectionalBar, Heatmap, PingIndicator, StatusDot, LiveLabel, FFTMiniChart, NumericTable
- [ ] Riprogettare `WatchlistPanel` full (pannello esistente) con sparkline per riga
- [ ] Integrare DashboardWorkspace in MainWindow (a cura di Paky)

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/marco.md` (spec personalità)

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai scoperto una limitazione/feature non documentata di Qt/pyqtgraph
3. Aggiungi a "Pattern di rendering scoperti" se hai trovato una tecnica riutilizzabile
4. Aggiorna "Task aperti"
