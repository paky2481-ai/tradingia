# Tom — Memoria operativa

> File aggiornato dall'agente Tom stesso al termine di ogni task.
> Tom legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-22: Progettato motore di esecuzione disciplinato (risk parity engine). Scelte: ERC (Equal Risk Contribution) come metodo allocazione pesi — derivazione completa con RC_i = w_i*(Sigma*w)_i/sigma_P, ottimizzazione quadratica con CCD; Ledoit-Wolf su T=252gg ricalcolo settimanale per covarianza; EWMA lambda=0.94 per vol realizzata; vol targeting sigma*=10% con cap leva 2x e smoothing beta=0.9; circuit breaker lineare a tratti d1=5% d2=15% floor=25% con rate-limit delta=2%/giorno in recupero. Look-ahead bias: tutte le stime chiuse a t-1.
- 2026-05-21: Round 2 validazione (`validate_signals_round2.py`). Momentum Tipo B: grid search 16 config IS/VAL (tutti Sharpe<0, massimo -0.226), OOS Sharpe=0.286 CAGR=+2.9% MDD=24.4% WF_stab=60%. FAIL su C1-B/C2/C3/C5/C6-B/C8 (T=564<750). Pairs: FDR sopravvissute QQQ/QQQM e HYG/SPY, entrambe FAIL OOS (Sharpe -2.76 e -0.08, N_trade<30). Bug trovato e corretto: is_end del momentum non va passato allo screening IS dei pairs (storia diversa). Segnali restano DISABLED.
- 2026-05-21: Implementati segnali concreti `MomentumCrossSectionalSignal` e `PairsMeanReversionSignal` in `strategies/signals/`. Quality gate 10/10 PASS. Validazione OOS su 15 anni daily (2011-2026): Momentum FAIL (C1: IC crossa zero, 53 trade); Pairs FAIL (6/8 criteri + K3/K4). Segnali restano disabled. Costi modellati: MOM 0.13% per leg, PAIRS 0.05% per leg + borrow.
- 2026-05-21: Progettato ABC `Signal` in `strategies/signal_base.py`. Architettura sibling di BaseStrategy (non subclass) per reggere CROSS_ASSET; adapter SignalStrategy per retrocompatibilità col Backtester; SignalOutput con score ∈ [-1,+1] e confidence ∈ [0,1]; ParamSpec per introspection GUI; stub MomentumCrossSectionalSignal e PairsMeanReversionSignal disabilitati finché VALIDATION_PROTOCOL §4 non è passato.
- 2026-05-14: Calibrate soglie confidenza pattern per asset class (commit `0519a43`); `AutoConfig.price_direction` migrato da `hurst > 0.5` a 20-bar return (no bias confermazione).
- 2026-05-21: Progettato protocollo di validazione statistica per momentum cross-sectional e pairs trading. Criteri PASS/FAIL numerici espliciti (8 criteri segnale singolo, 8 per ensemble). Include DSR (Bailey-Lopez de Prado), Hansen SPA, walk-forward 5+ finestre, gestione look-ahead bias, baseline confrontabile metodologicamente corretta. Killer criteria K1-K5 per invalidazione immediata indipendente dalla statistica.
- 2026-05-20: Bug A (OHLCV outlier): aggiunta `sanitize_ohlcv` in `data/feed.py`, clamping `LOW_RATIO_FLOOR=0.75` applicato centralmente in `get_ohlcv`. Bug B (resample 4h): corretto `"4H"` → `"4h"` in `utils/timeframes.py`. Quality gate: 3/3 test PASS.
- 2026-05-20: Validazione statistica pattern (script `scripts/validate_patterns.py`): walk-forward 5 finestre, 11 simboli, 10y daily. 16/22 pattern superano FDR (BH alpha=0.05). Pattern forti: Bullish/Bearish Engulfing, Hammer, Morning/Evening Star, Falling Wedge. Pattern senza edge: Doji, Ascending/Descending Triangle. Sistema NON pronto per capitale reale: avg_move ≈ +0.0% (slippage 1-bar non modellato).
- 2026-05-20: Backtest realistico (`scripts/validate_patterns_net_return.py`): entry open+1, stop=invalidation_price, costi round-trip per asset class, P&L netto per trade. Risultato: 2/21 pattern con CI 95% > 0 e FDR sig: Doji (+0.51%, N=5026) e Ascending Triangle (+1.91%, N=764). Ma Doji e' anomalia (neutral, nessuna direzione). 19/21 pattern NEGATIVI netti. Verdetto: NESSUN edge economico robusto nei pattern candlestick daily. Report precedente (97% hit) era artefatto di definizione: baseline e pattern usavano criteri di hit incomparabili.

## Lezioni apprese (permanenti)

- **Risk parity — limiti strutturali:** ERC garantisce diversificazione del rischio ma NON protegge dai gap overnight, NON anticipa il collasso delle correlazioni in crisi (tutti gli asset verso rho=+1), NON outperforma necessariamente senza leva sulle obbligazioni. La leva sui bond (cuore del risk parity classico) genera perdite severe in regime di tassi in salita (2022). Valutare sempre su ciclo completo di tassi.
- **Covarianza LW vs obiettivo portafoglio:** Ledoit-Wolf minimizza l'errore Frobenius sulla matrice, non l'errore sui pesi ERC. Le due perdite non sono equivalenti. LW funziona bene empiricamente ma la garanzia teorica e' piu' debole di quanto appaia.

- **Momentum cross-sectional OOS 2022-2025 (11 ETF daily):** Sharpe 0.72, CAGR +13%, MDD 17.7%. MA: CI 95% rendimento per trade crossa zero (N=53). Il segnale e' quasi sempre investito (96% bar): cattura il beta del mercato piu' che un alpha. Confronto con baseline random (Sharpe=0.096) suggerisce qualche edge, ma la potenza statistica e' insufficiente. FAIL C1.
- **Momentum Round 2 (42 ETF, Tipo B, 2018-2026, OOS 2023-2026):** Grid search IS/VAL: TUTTI 16 config con Sharpe negativo (-0.226 migliore). Segnale momentum long/short cross-sectional e' sistematicamente DISTRUTTIVO in IS su questo universo e periodo. OOS: Sharpe=0.286, CAGR=+2.9%, MDD=24.4%, WF stability=60% (solo 3/5 finestre positive). FAIL per insufficienza vs soglie e T=564 < 750. DSR p=0.000004 (PASS) e' anomalo: cattura variance dei rendimenti, non edge. La volatilita' alternata delle finestre WF (+1.56, -1.57, +0.37, -2.20, +2.99) segnala segnale instabile.
- **Pairs Round 2 (14 coppie, §13):** FDR su IS 60% (2010-2016): solo QQQ/QQQM e HYG/SPY sopravvivono. QQQ/QQQM arbitraggio quasi-puro (HL=0.3gg): OOS Sharpe=-2.76, N_trade=18. HYG/SPY: OOS Sharpe=-0.08, N_trade=5. Entrambe FAIL tutti i criteri non-triviali. SPA: stat=-0.08 p=0.48 FAIL.
- **DSR segno corretto:** con n_configs=1, DSR = t-statistico di Sharpe. p_value corretto = 1 - Phi(DSR). Usare Phi(DSR) produce p=1.0 per SR>0 (errore di segno).
- **Pattern recognition — risultato empirico AGGIORNATO:** Il 97% hit rate era artefatto: baseline usava "move > 0" (test di direzione), i pattern usavano "tocco target geometrico entro 20 barre" — confronto apples-to-oranges. Con backtest realistico (entry open+1, stop a invalidation_price, costi round-trip per asset class): 2/21 pattern sopravvivono con CI 95% > 0 (Doji +0.51% neutro, Ascending Triangle +1.91%). I 19 candlestick classici (Hammer, Engulfing, Morning Star, ecc.) hanno expected return NETTO NEGATIVO. NON collegare capitale reale ai pattern candlestick daily senza filtri regime/volume aggiuntivi.
- **Ensemble e gradi di liberta':** con K segnali e SR target = 0.5, il numero minimo di osservazioni OOS per evitare overfitting e' T_min = K*log(K)/SR^2. Per K=3 e SR=0.5: T_min ≈ 13 anni di dati settimanali. Usare always equal-weight o inverse-volatility come pesi a priori. MAI ottimizzare i pesi su OOS.
- **DSR (Deflated Sharpe Ratio):** usare Bailey-Lopez de Prado 2014 come test principale contro data-snooping. N nel calcolo SR_0 deve includere OGNI configurazione esplorata in IS, incluse quelle scartate. Implementazione: mlfinlab.statistics.sharpe_ratio.deflated_sharpe_ratio.

- **is_end mismatch nel pairs screening:** se momentum e pairs hanno panel con storia diversa (inner join diverso), il is_end del momentum NON va passato allo screening IS dei pairs. Ogni coppia deve calcolare is_end = int(n_barre_comuni * IS_FRAC) sulla propria serie. Errore subdolo: passa silenziosamente ma usa solo il 28% della storia disponibile.
- **Pairs "arbitraggio puro" (SPY/IVV, GLD/IAU):** beta~1, spread std~0.02%, rho_AR1 negativo. Il modello AR(1) non stima una half-life significativa (rho<0 o >1) non per un bug ma perche lo spread e' rumore bianco con media~0. ADF p~0 perche la serie e quasi costante. Questi pair non generano segnali tradabili a frequenza daily. Il FDR li seleziona ma poi falliscono in OOS per mancanza di trade.
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

## Task aperti (aggiornato 2026-05-22)

- [x] Validazione statistica pattern su mercati reali (con Chloe) — COMPLETATA 2026-05-20
- [x] Stimare avg_move netto dopo slippage 1-bar e commissioni per pattern significativi — COMPLETATA 2026-05-20 (script validate_patterns_net_return.py)
- [ ] Analisi stabilita' temporale pattern: regime bull vs bear (2020 crash, 2022 bear)
- [ ] Aggiungere segnali nel SignalBus: `ai_result`, `kelly_update`, `regime_update`, `loop_heartbeat`, `correlation_update` (vedi piano GUI refactor)
- [ ] Implementazione motore risk parity: ERC solver (scipy.optimize + CCD), LedoitWolf rolling, EWMA vol, vol targeting, circuit breaker drawdown — design matematico completato 2026-05-22, pronto per implementazione Paky
- [x] Progettare ABC Signal + SignalOutput + ParamSpec + SignalStrategy adapter — COMPLETATO 2026-05-21
- [x] Implementare MomentumCrossSectionalSignal + PairsMeanReversionSignal + validate_signals.py — COMPLETATO 2026-05-21. ENTRAMBI FAIL su OOS. Segnali restano disabled.
- [x] Round 2 validazione con §12 (Tipo B) e §13 (FDR+SPA) — COMPLETATO 2026-05-21. Script: `scripts/validate_signals_round2.py`. Risultato: entrambi FAIL. Segnali restano DISABLED.
- [ ] Esporre `CycleAnalysis.fft_spectrum` come API consumibile dal nuovo `FFTMiniChart` widget GUI

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/tom.md` (spec personalità)

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai dimostrato matematicamente un'insidia non documentata
3. Aggiungi a "Modelli e parametri ottimali noti" se hai trovato configurazione validata
4. Aggiorna "Task aperti"
