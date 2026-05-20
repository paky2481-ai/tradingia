# Tom — Memoria operativa

> File aggiornato dall'agente Tom stesso al termine di ogni task.
> Tom legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Calibrate soglie confidenza pattern per asset class (commit `0519a43`); `AutoConfig.price_direction` migrato da `hurst > 0.5` a 20-bar return (no bias confermazione).
- 2026-05-20: Bug A (OHLCV outlier): aggiunta `sanitize_ohlcv` in `data/feed.py`, clamping `LOW_RATIO_FLOOR=0.75` applicato centralmente in `get_ohlcv`. Bug B (resample 4h): corretto `"4H"` → `"4h"` in `utils/timeframes.py`. Quality gate: 3/3 test PASS.
- 2026-05-20: Validazione statistica pattern (script `scripts/validate_patterns.py`): walk-forward 5 finestre, 11 simboli, 10y daily. 16/22 pattern superano FDR (BH alpha=0.05). Pattern forti: Bullish/Bearish Engulfing, Hammer, Morning/Evening Star, Falling Wedge. Pattern senza edge: Doji, Ascending/Descending Triangle. Sistema NON pronto per capitale reale: avg_move ≈ +0.0% (slippage 1-bar non modellato).
- 2026-05-20: Backtest realistico (`scripts/validate_patterns_net_return.py`): entry open+1, stop=invalidation_price, costi round-trip per asset class, P&L netto per trade. Risultato: 2/21 pattern con CI 95% > 0 e FDR sig: Doji (+0.51%, N=5026) e Ascending Triangle (+1.91%, N=764). Ma Doji e' anomalia (neutral, nessuna direzione). 19/21 pattern NEGATIVI netti. Verdetto: NESSUN edge economico robusto nei pattern candlestick daily. Report precedente (97% hit) era artefatto di definizione: baseline e pattern usavano criteri di hit incomparabili.

## Lezioni apprese (permanenti)

- **Pattern recognition — risultato empirico AGGIORNATO:** Il 97% hit rate era artefatto: baseline usava "move > 0" (test di direzione), i pattern usavano "tocco target geometrico entro 20 barre" — confronto apples-to-oranges. Con backtest realistico (entry open+1, stop a invalidation_price, costi round-trip per asset class): 2/21 pattern sopravvivono con CI 95% > 0 (Doji +0.51% neutro, Ascending Triangle +1.91%). I 19 candlestick classici (Hammer, Engulfing, Morning Star, ecc.) hanno expected return NETTO NEGATIVO. NON collegare capitale reale ai pattern candlestick daily senza filtri regime/volume aggiuntivi.

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

- [x] Validazione statistica pattern su mercati reali (con Chloe) — COMPLETATA 2026-05-20
- [x] Stimare avg_move netto dopo slippage 1-bar e commissioni per pattern significativi — COMPLETATA 2026-05-20 (script validate_patterns_net_return.py)
- [ ] Analisi stabilita' temporale pattern: regime bull vs bear (2020 crash, 2022 bear)
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
