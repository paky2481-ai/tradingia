# TradingIA — Protocollo di Validazione dei Segnali

> Redatto da Tom (statistica) + Chloe (mercato reale), consolidato da Max — 2026-05-21.
> Questo documento va definito e congelato PRIMA di implementare qualsiasi segnale.
> Nessun segnale entra in una strategia operativa senza aver superato questo protocollo.

## Premessa onesta

Eliminare il fattore umano (disciplina di esecuzione, rischio, timing) è una condizione
**necessaria ma non sufficiente**. Un sistema perfettamente disciplinato che gira su segnali
senza edge perde comunque — solo in modo più ordinato. La gestione del rischio è il
*moltiplicatore* di un edge esistente, non il suo *generatore*. Questo protocollo serve a
distinguere un edge reale da un artefatto statistico, come abbiamo fatto coi pattern
(2026-05-20: 19/21 pattern bocciati).

---

## 1. Definizione formale dei segnali

### Segnale A — Momentum cross-sectional

```
Mom_adj(i, t) = [ P(i, t-S) / P(i, t-L) ] - 1
```

- `S = 5` barre (skip recente, neutralizza il mean-reversion di brevissimo termine)
- `L` = lookback parametrico (range da esplorare in-sample)
- Ranking cross-sectional: long sul top quantile, short sul bottom quantile
- Filtro regime via **z-score rolling del VIX** (non soglia fissa: una soglia fissa è
  fragile e implicitamente ottimizzata).

### Segnale B — Mean reversion su spread cointegrati (pairs)

Tre step obbligatori, nessuno saltabile:
1. **ADF individuale** su ciascuna serie → conferma che entrambe sono I(1).
2. **Regressione di cointegrazione su log-prezzi** (non prezzi grezzi: stabilizza la varianza).
3. **ADF sui residui** → conferma la stazionarietà dello spread.

- z-score con media e std **rolling** (media/std full-sample = look-ahead bias).
- Half-life dello spread: `tau = -log(2) / log(rho_AR1)`. Se `tau` > orizzonte del trade, il pair è inutile.

---

## 2. Universo asset e bias di selezione

- **Composizione point-in-time**: l'universo a ogni data `t` deve essere quello *storico*,
  non quello attuale. Il survivorship bias su 20 anni vale ~1-2% annuo di rendimento fittizio.
- Il momentum cross-sectional richiede un paniere ampio → verificare la copertura reale
  del broker IG (vincolo pratico, vedi §7).
- I pairs non vanno scelti col senno di poi: la lista candidata va fissata *prima* di
  vedere i risultati.

---

## 3. Split temporale

- Schema **60 / 10 / 30** — In-Sample / Validation / Out-of-Sample.
- **Walk-forward** a finestra espandente, minimo **5 finestre OOS** da 6-12 mesi.
- Risultato di riferimento = **equity curve OOS concatenata**, NON la media degli Sharpe per finestra.
- Il periodo OOS si esegue **una volta sola**. Ogni modifica dopo aver visto l'OOS lo contamina.

---

## 4. Metrica di decisione — criteri PASS/FAIL per segnale singolo

Tutti e 8 obbligatori (un solo FAIL = segnale respinto):

| # | Criterio | Soglia |
|---|----------|--------|
| 1 | Intervallo confidenza 95% del rendimento netto/trade (bootstrap 3000) | > 0 |
| 2 | Sharpe Ratio (OOS, netto) | > 0.5 |
| 3 | Sortino Ratio (OOS, netto) | > 0.7 |
| 4 | Max Drawdown | < 25% |
| 5 | Calmar Ratio | > 0.3 |
| 6 | Numero di trade | >= 50 |
| 7 | Deflated Sharpe Ratio — p-value | < 0.05 |
| 8 | Stabilità walk-forward (finestre con SR > 0) | >= 80% |

**Il numero che decide è il rendimento NETTO per trade dopo costi reali.** Tutto il resto qualifica.

---

## 5. Difesa contro il data-snooping

Tre livelli, non sostituibili tra loro:
- **Deflated Sharpe Ratio** (Bailey-López de Prado): corregge lo Sharpe per il numero di
  configurazioni testate in-sample.
- **Hansen SPA** (evoluzione del White's Reality Check): bootstrap stazionario a blocchi di
  lunghezza ~`sqrt(T)`.
- **FDR Benjamini-Hochberg**: correzione per multiple testing sulla selezione di feature in-sample.

---

## 6. Look-ahead bias — errori vietati

1. Stimare il beta di cointegrazione su tutto il dataset e poi "validare" su una sottoparte. **(il più insidioso per noi)**
2. Media/std dello z-score full-sample invece che rolling.
3. Filtro VIX che usa il valore di chiusura per decidere l'ingresso sulla stessa barra.
4. Ranking momentum che include la barra di esecuzione.
5. Universo asset costruito con la composizione di indice attuale.

---

## 7. Vincoli di mercato reale (Chloe)

### Costi da modellare — obbligatori nel backtest

- Spread bid/ask per asset class, commissioni, slippage realistico.
- **Borrow cost / costo dello short** sulle gambe short.
- **Financing CFD overnight** — il costo silenzioso che i paper backtest omettono.
  Esempio pairs: holding ~15 giorni, nozionale $20k → **$25-35 per trade** di solo financing,
  prima di spread e commissioni. Ometterlo gonfia i risultati del 15-20%.

### Soglia di sopravvivenza del momentum

Costi round-trip ~0.6% per rotazione mensile → il momentum **lordo** deve generare almeno
**1.8%/mese (3x i costi)** per sopravvivere a slippage e spread reale. Sotto questa soglia
siamo di nuovo nel territorio dei pattern: edge apparente che evapora coi costi.

### Trappola del filtro VIX

Backtestare *solo* i periodi in cui il filtro era attivo introduce un survival selection bias.
Il backtest corretto **include i periodi di inattività** (drawdown zero, NON guadagno zero)
nel calcolo di Sharpe e CAGR annualizzato.

### Capienza, liquidità, regime

- Verificare che la strategia regga con capitale crescente; escludere asset illiquidi.
- Momentum crash documentati: marzo 2009, aprile 2020 — il backtest DEVE includerli.
- Crowding risk del momentum: non catturabile dal backtest, da tenere presente come rischio noto.

---

## 8. Validazione della combinazione (ensemble)

Il punto critico: combinare segnali aumenta i gradi di libertà.

- Stimare i pesi su OOS richiede dati enormi (con K=3 segnali e SR target 0.5: ~13 anni di
  dati settimanali). **Quindi i pesi NON si ottimizzano su OOS.**
- Pesi **fissi a priori**: equal-weight oppure inverse-volatility.
- I criteri PASS/FAIL dell'ensemble sono **30-40% più severi** di quelli del segnale singolo
  (compensano i gradi di libertà aggiunti). Prerequisito B0: ogni segnale dell'ensemble deve
  aver già passato il §4 in isolamento.

---

## 9. Killer criteria — invalidazione immediata

Indipendenti dalla statistica. Anche un solo KO = segnale respinto:
- **K1** — performance concentrata in <= 3 trade.
- **K2** — drawdown massimo collocato nell'ultimo trimestre OOS.
- **K3** — risultato che ribalta segno tra finestra IS e finestra OOS.
- **K4** — N trade insufficiente a rendere lo Sharpe interpretabile.
- **K5** — edge che sparisce applicando i costi reali del §7.

---

## 10. Criteri di KILL in paper trading

Una volta in paper trading live, un segnale viene dichiarato morto se:
- il drawdown supera quello massimo registrato in OOS;
- la performance live diverge significativamente dal backtest (test di rottura);
- la cointegrazione del pair si rompe (ADF rolling sui residui non più significativo).

---

## 11. Ordine di esecuzione (11 step)

1. Congelare questo protocollo. → 2. Costruire l'universo point-in-time. → 3. Definire la
lista candidata pairs / parametri momentum. → 4. Esplorazione in-sample (60%). → 5. Tuning
su validation (10%). → 6. Congelare i parametri. → 7. **Eseguire OOS una sola volta.** →
8. Applicare §4 + §7 + §9. → 9. Se PASS: ensemble §8. → 10. Paper trading con criteri §10. →
11. Live solo dopo paper trading positivo.

---

## 12. Tipizzazione del segnale — REVISIONE 2026-05-21

> Aggiunta dopo la supervisione del round 1: il criterio C1 era mal-specificato per i
> segnali a esposizione continua. I criteri §4 vanno applicati secondo il *tipo* di segnale.

Ogni segnale va classificato prima della validazione:

### Tipo A — EVENT-DRIVEN (apri → chiudi → flat → attendi)
Esempi: pattern recognition, pairs mean reversion. Il "trade" è un'unità naturale e discreta.
- **C1 valido così com'è**: bootstrap CI 95% sul rendimento netto *per trade*.
- I criteri §4 restano invariati.

### Tipo B — ALWAYS-IN / continuo (esposizione quasi permanente, ribilanciata)
Esempi: momentum cross-sectional. Il portafoglio è quasi sempre investito; i "trade" sono
solo partizioni arbitrarie di una serie di rendimenti continua. Spezzettare in N trade e
fare un CI sulla media *distrugge potenza statistica* (N osservazioni invece di T).
- **C1 sostituito da C1-B**: bootstrap CI 95% sul **rendimento periodico medio** (daily o
  weekly) calcolato sull'intera serie di rendimenti OOS. La numerosità è T (la serie
  completa), non il numero di rotazioni.
- **Il criterio decisionale primario diventa C2+C7** (Sharpe netto + DSR sui rendimenti
  periodici): è la statistica con la potenza adeguata per un segnale continuo.
- C6 (N trade ≥ 50) reinterpretato: per un Tipo B conta T ≥ 750 osservazioni periodiche.

### DSR — uso corretto di `n_configs`
Il Deflated Sharpe Ratio defleziona *solo* se `n_configs` riflette il numero **reale** di
configurazioni esplorate in-sample. `n_configs = 1` annulla la deflazione e riduce il C7
a un semplice t-test — vietato dichiararlo se è stata fatta una qualsiasi grid search.
**Regola**: ogni combinazione di parametri testata in IS/VAL va contata; `n_configs` =
dimensione totale della griglia esplorata. Se l'OOS è stato osservato in un round
precedente, va contato anche quel "tentativo" — l'unico modo onesto di ri-usare un OOS è
gonfiare `n_configs` per pagarne il costo statistico.

---

## 13. Validazione su universo di candidati (pairs round 2)

Quando si seleziona il miglior candidato da un universo (es. la coppia cointegrata più
promettente tra molte), il data-snooping è massimo. Procedura obbligatoria:

1. **Lista candidati definita a priori** per ragioni economiche, *prima* di vedere i dati —
   non data-mined su tutte le combinazioni possibili.
2. **Screening cointegrazione su IS soltanto**. p-value ADF di tutti i candidati.
3. **Correzione FDR Benjamini-Hochberg** sui p-value di cointegrazione: controlla la quota
   di falsi positivi nella selezione.
4. **Hansen SPA** sul candidato selezionato: il suo Sharpe OOS va confrontato con la
   distribuzione del *massimo* Sharpe ottenibile per puro caso sull'intero universo testato.
5. Un pair "vince" solo se sopravvive a §4 (Tipo A) **e** a FDR **e** a SPA.
