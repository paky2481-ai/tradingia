# Chloe — Memoria operativa

> File aggiornato dall'agente Chloe stesso al termine di ogni task.
> Chloe legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Confermati 7 strumenti operativi: EUR/USD, GBP/USD, XAU/USD, S&P, DAX, EUR/GBP, USD/JPY. Liquidi e con spread bassi.
- 2026-05-14: Strategia split: trend_4h per forex/indici/oro, range_1h per cross laterali (EUR/GBP, USD/JPY).
- 2026-05-20: Analisi validazione pattern (Tom): win rate 97% su avg_move=0% è un falso edge — target geometrico minuscolo tocca rumore di mercato, non segnale predittivo. Sistema NON tradeable fino a integrazione di stop loss reali e costi di transazione nel backtest.
- 2026-05-20: Verdetto finale pattern recognition: 19/21 netti negativi dopo costi realistici. Ascending Triangle +1.91% = data-snooping su SPY/QQQ/AAPL in bull market. Sistema accantonato come segnale primario. Alpha reale: momentum cross-sectional con filtro VIX, oppure mean reversion su spread cointegrati.
- 2026-05-21: Definiti vincoli di mercato reale per protocollo validazione momentum + pairs trading. Costi round-trip ETF mensile: 0.4–0.8%. Financing CFD IG: ~3% annuo (0.12% per trade a 15gg holding). Pairs candidati: SPY/QQQ, EUR/USD/GBP/USD. Kill criteria definiti in forma esplicita e non negoziabile prima del paper trading.
- 2026-05-21: CONGELATO universo round 2 — MOMENTUM: 42 ETF in 7 gruppi (settoriale USA XL*, equity internazionale, fixed income, commodity, REIT, valute ETF, vol/factor). PAIRS: 14 coppie in 4 categorie (doppio provider, competitor diretti, settoriali complementari, macro cross-asset). Lista fissa prima che Tom veda i dati — qualsiasi modifica successiva invalida il protocollo §13.
- 2026-05-21: Scritto artefatto verificabile `docs/ROUND2_UNIVERSE.md` con tutti i 42 ticker (nome esteso + gruppo + motivazione) e le 14 coppie (ticker + legame economico). 5 coppie marcate [RISCHIO ROTTURA]: QQQ/QQQM (storia corta), MSFT/GOOGL (AI disruption), TLT/GLD (regime-conditional), EEM/GLD (legame debole), HYG/SPY (stress creditizio). Costi di trading per asset class documentati in coerenza con §7.
- 2026-05-22: Progettata architettura MERCATO/RISCHIO del motore di esecuzione disciplinato (E1). Universo all-weather 8 ETF con storia dal 2003+, vol target 10% annuo non levered, ribilanciamento ibrido (mensile + soglia 5%), circuit breaker a -8%/-15%, filtro regime su vol realizzata (non solo VIX). Costi round-trip stimati 0.06-0.14% per i-class. Limite critico documentato: 2022 ha dimostrato che azioni+bond possono correggere insieme — il modello non è immune, solo meno peggio dell'umano emotivo.

## Lezioni apprese (permanenti)

- **Pattern candlestick:** funzionano meglio su daily/weekly. Su 1m/5m è rumore. Mai trade su candlestick singolo, sempre conferma.
- **TTL pattern:** `ttl_bars=10` può essere conservativo per crypto (più veloci) e troppo aggressivo per indici (più lenti). Calibrare per asset class.
- **Sessioni operative:** forex liquido 07:00-21:00 UTC, indici 08:00-21:30 UTC, commodity 08:00-20:00 UTC. Fuori orario: solo monitoraggio.
- **Slippage realistico:** stimare 1-2 pip su forex liquidi, 0.5-1 punti su indici, 0.20-0.50$ su oro. Nel backtest se non lo modelli, i risultati sono ottimistici.
- **Correlazioni nascoste:** EUR/USD e GBP/USD correlazione ~0.7 → mai entrambe long allo stesso tempo (raddoppia il rischio).
- **VIX > 25:** ridurre size del 50%. VIX > 35: solo strategie mean-rev, no breakout.
- **Win rate alto + avg_move zero = trappola**: target geometrico minuscolo genera hit rate artificialmente alto. L'unica metrica che conta è E[P&L netto] = (win_rate × avg_win) - (loss_rate × avg_loss) - costi. Se avg_move è zero, E[P&L] è negativo per definizione dopo i costi.
- **Bull market bias nei pattern di inversione**: su dati 2015-2025 i pattern bullish (Engulfing, Morning Star) sembrano funzionare perché il mercato tende a salire comunque. Testare sempre su regimi bear e alta volatilità separati prima di trarre conclusioni.
- **Candlestick pattern = zero edge su mercati moderni**: con HFT e algo che leggono gli stessi pattern, il segnale viene arbitraggiato prima dell'esecuzione. Edge documentato robusto: momentum cross-sectional (1-12 mesi) e mean reversion su spread cointegrati.
- **Cointegrazione su pairs**: va testata con Johansen rolling (finestra 252gg, ricalcolo ogni 60gg). Half-life > 30gg = pair non tradable. Hedge ratio che cambia > 20% in 60gg = segnale di rottura strutturale. Il selection bias è il pericolo principale: scegliere pairs guardando l'intera storia è look-ahead bias — separare periodo A (selection) da periodo B (test) obbligatoriamente.
- **Filtro VIX per momentum**: kill a VIX > 40, size 50% a VIX > 30. Ma il VIX da solo non basta — aggiungere VIX term structure (backwardation = stress acuto) e VIX ROC > 30% in 5gg come trigger aggiuntivi di riduzione. Rientro graduale: 25% size ogni 5gg solo se VIX < 25 AND indice > 200MA.

## Domande critiche da farsi sempre

1. "C'è look-ahead bias?"
2. "Lo slippage è realistico?"
3. "Le posizioni sono correlate?"
4. "Funzionerebbe in un mercato diverso (ottimizzato su SPY → funziona su DAX)?"
5. "Il sample è abbastanza grande (>100 trade)?"

## Task aperti

- [x] Validazione statistica pattern su mercati reali (con Tom) — COMPLETATO, risultati analizzati
- [ ] PatternBacktester: integrare invalidation_price come stop loss e calcolare avg_loss / R:R ratio reale — BASSA PRIORITA' (pattern non ha edge primario)
- [ ] Implementare momentum cross-sectional su paniere 42 ETF (universo congelato in docs/ROUND2_UNIVERSE.md) con filtro VIX a 3 livelli
- [ ] Implementare pairs trading su 14 coppie (universo congelato in docs/ROUND2_UNIVERSE.md) — screening cointegrazione solo su IS 60%, poi FDR + SPA per selezione
- [ ] Aggiungere costi di transazione per asset class nel backtest (0.15% azioni, 0.05% forex major, 0.20% crypto round-trip)
- [ ] Separare backtest per regime (trending/ranging/alta vol) per isolare dove l'edge è concentrato
- [ ] Backtesting walk-forward su dati 2020-2025 per verificare robustezza strategie
- [ ] Definire trailing stop dinamico basato su ATR invece di percentuale fissa
- [ ] Revisione asset class config per mercato corrente (2026)

## Workflow

All'inizio di ogni sessione:
1. Leggi questa memoria + il file `agents/chloe.md` (spec personalità)

Alla fine di ogni task:
1. Aggiungi 1-3 righe in "Decisioni recenti" (rimuovi le più vecchie se >20)
2. Aggiungi a "Lezioni apprese" SOLO se hai osservato un comportamento di mercato non documentato
3. Aggiorna "Task aperti"
