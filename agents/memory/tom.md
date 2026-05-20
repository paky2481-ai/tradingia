# Tom — Memoria operativa

> File aggiornato dall'agente Tom stesso al termine di ogni task.
> Tom legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Calibrate soglie confidenza pattern per asset class (commit `0519a43`); `AutoConfig.price_direction` migrato da `hurst > 0.5` a 20-bar return (no bias confermazione).
- 2026-05-20: Bug A (OHLCV outlier): aggiunta `sanitize_ohlcv` in `data/feed.py`, clamping `LOW_RATIO_FLOOR=0.75` applicato centralmente in `get_ohlcv`. Bug B (resample 4h): corretto `"4H"` → `"4h"` in `utils/timeframes.py`. Quality gate: 3/3 test PASS.

## Lezioni apprese (permanenti)

- **yfinance OHLCV glitch:** feed restituisce occasionalmente low/high fuori scala (es. GBPUSD=X 2012-01-23: low=0.637 vs corpo ~1.55). Discriminante: `low/min(open,close)`. Glitch: 0.41; crash reale estremo (Truss 2022): 0.96. Soglia conservativa 0.75 lascia 21% di margine sopra il caso peggiore reale osservato. Strategia: clamping (non rimozione) per preservare continuità temporale (LSTM, FFT).
- **Hurst exponent:** la stima R/S è affidabile da N≥200 osservazioni. Sotto, alta varianza.
- **FFT cycle detection:** dominante affidabile solo se SNR > 3. Sotto, è rumore — meglio non usarlo per timing.
- **TimeframeSelector ideal_cycle_bars=20**: riferimento per indicatori standard (RSI 14, MACD 12-26-9 son scelti per cicli ~20-bar).
- **Look-ahead bias:** nel `PatternBacktester` usare obbligatoriamente loop bar-by-bar con `iloc[:i+1]`. MAI calcolare indicatori sull'intero df e poi shiftare.
- **Walk-forward validation:** SGD online (`MetaLearner`) è preferibile al batch retraining per evitare overfitting al regime corrente.
- **Kelly criterion:** mai usare il Kelly pieno — fractional Kelly (1/4 o 1/2) per ridurre drawdown.

## Modelli e parametri ottimali noti

- LSTM TradingIA: `seq_len=60, hidden=64, layers=2, dropout=0.2` — buon trade-off
- Random Forest: `n_estimators=200, max_depth=8` — overfit oltre
- Ensemble: media pesata 60% LSTM + 40% RF su mercati trending; viceversa su mean-rev

## Task aperti

- [ ] Validazione statistica pattern su mercati reali (con Chloe)
- [ ] Aggiungere segnali nel SignalBus: `ai_result`, `kelly_update`, `regime_update`, `loop_heartbeat`, `correlation_update` (vedi piano GUI refactor)
- [ ] Esporre `CycleAnalysis.fft_spectrum` come API consumibile dal nuovo `FFTMiniChart` widget GUI

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/tom.md` (spec personalità)

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai dimostrato matematicamente un'insidia non documentata
3. Aggiungi a "Modelli e parametri ottimali noti" se hai trovato configurazione validata
4. Aggiorna "Task aperti"
