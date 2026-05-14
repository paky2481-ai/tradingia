# Chloe — Memoria operativa

> File aggiornato dall'agente Chloe stesso al termine di ogni task.
> Chloe legge questo file all'inizio di ogni sessione per recuperare contesto.

## Decisioni recenti (max 20, FIFO)

- 2026-05-14: Confermati 7 strumenti operativi: EUR/USD, GBP/USD, XAU/USD, S&P, DAX, EUR/GBP, USD/JPY. Liquidi e con spread bassi.
- 2026-05-14: Strategia split: trend_4h per forex/indici/oro, range_1h per cross laterali (EUR/GBP, USD/JPY).

## Lezioni apprese (permanenti)

- **Pattern candlestick:** funzionano meglio su daily/weekly. Su 1m/5m è rumore. Mai trade su candlestick singolo, sempre conferma.
- **TTL pattern:** `ttl_bars=10` può essere conservativo per crypto (più veloci) e troppo aggressivo per indici (più lenti). Calibrare per asset class.
- **Sessioni operative:** forex liquido 07:00-21:00 UTC, indici 08:00-21:30 UTC, commodity 08:00-20:00 UTC. Fuori orario: solo monitoraggio.
- **Slippage realistico:** stimare 1-2 pip su forex liquidi, 0.5-1 punti su indici, 0.20-0.50$ su oro. Nel backtest se non lo modelli, i risultati sono ottimistici.
- **Correlazioni nascoste:** EUR/USD e GBP/USD correlazione ~0.7 → mai entrambe long allo stesso tempo (raddoppia il rischio).
- **VIX > 25:** ridurre size del 50%. VIX > 35: solo strategie mean-rev, no breakout.

## Domande critiche da farsi sempre

1. "C'è look-ahead bias?"
2. "Lo slippage è realistico?"
3. "Le posizioni sono correlate?"
4. "Funzionerebbe in un mercato diverso (ottimizzato su SPY → funziona su DAX)?"
5. "Il sample è abbastanza grande (>100 trade)?"

## Task aperti

- [ ] Validazione statistica pattern su mercati reali (con Tom)
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
