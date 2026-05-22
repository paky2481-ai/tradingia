# TradingIA — Design del Motore di Esecuzione Disciplinato (E1)

> Consolidato da Max — 2026-05-22. Input: Chloe (mercato/rischio) + Tom (matematica).
> Documento di design della fase E1. Da rivedere con l'utente prima di implementare E2.

## 1. Obiettivo e filosofia

Dopo aver dimostrato con rigore che pattern, pairs e momentum non hanno edge predittivo,
il sistema **non cerca più di prevedere il mercato**. Il motore cattura i premi per il
rischio (equity risk premium, diversificazione) in modo disciplinato e senza errori umani.

> Non promette di battere il mercato. Promette di catturare ciò che il mercato offre
> davvero, senza che paura e avidità lo rovinino. Lo svantaggio comportamentale medio del
> retail è 1.5-2%/anno (Dalbar QAIB 2023): il motore recupera *quello*, non genera alpha.

## 2. Universo asset — 8 ETF all-weather (Chloe)

Paniere diversificato per *fonti di rischio*, costruito per coprire i quattro regimi
macro (crescita / recessione / inflazione / stagflazione), non per indovinarne uno.

| Blocco | Ticker | Ruolo | Storia |
|--------|--------|-------|--------|
| Equity USA | SPY | Premio equity, crescita USA | 1993 |
| Equity sviluppati ex-US | VEA | Diversificazione geografica/valutaria | 2007 |
| Equity emergenti | VWO | Premio mercati emergenti | 2005 |
| Treasury lungo | TLT | Hedge deflazione/recessione | 2002 |
| Treasury intermedio | IEF | Duration media, smoothing | 2002 |
| TIPS | TIP | Hedge inflazione (regge dove TLT crolla) | 2003 |
| Oro | GLD | Safe haven, hedge stagflazione | 2004 |
| Commodity broad | DJP | Inflazione fisica | 2006 |

Storia comune del backtest: **dal 2006** (DJP è il più recente). Copre GFC 2008, Covid 2020,
shock 2022. Tutti liquidi, nessun survivorship bias (broad index, non settoriali scelti col
senno di poi).

## 3. Allocazione dei pesi — Equal Risk Contribution (Tom)

Metodo scelto: **ERC (Equal Risk Contribution)**. Ogni asset contribuisce la stessa quota
di rischio totale. Non richiede alcuna previsione dei rendimenti attesi — è il punto del pivot.

- Contributo di rischio: `RC_i = w_i · (Σw)_i / σ_P`, dove `σ_P = √(wᵀΣw)`.
- Pesi ERC: si risolvono imponendo `RC_i = RC_j ∀ i,j`, via ottimizzazione quadratica con
  cyclical coordinate descent (CCD).
- Effetto: in un 60/40 classico l'equity porta ~90% del rischio; con ERC ogni blocco pesa
  uguale in rischio → niente concentrazione nascosta.

**Matrice di covarianza**: stimatore **Ledoit-Wolf shrinkage** su finestra T=252 giorni,
ricalcolata settimanalmente. Lo shrinkage stabilizza una matrice notoriamente rumorosa.
(Limite noto, da Tom: LW minimizza l'errore sulla matrice, non sui pesi ERC — garanzia
teorica più debole di quanto sembri, ma robusta empiricamente.)

## 4. Vol targeting — UNLEVERED (conflitto risolto da Max)

Esposizione complessiva scalata per tenere la volatilità di portafoglio al bersaglio:

`scaling_t = σ_target / σ_realizzata_t`

- `σ_realizzata` stimata via EWMA con λ=0.94 (finestra ~21gg, scende a ~10gg in stress VIX>30).
- **Scaling vincolato a [0, 1] — nessuna leva.** Tom aveva proposto cap leva 2x; Chloe ha
  argomentato contro (costo finanziamento retail 6-8%/anno, rischio margin call proprio
  durante le crisi). **Decisione Max: il motore resta unlevered.** Quando la vol realizzata
  è sotto il target i pesi restano al 100%; quando è sopra, l'esposizione si riduce e il
  resto va in liquidità. La leva resta una possibile evoluzione futura, solo con conto
  futures (ES/ZN/GC) — non con conto a margine equity.
- Smoothing del fattore di scaling con β=0.9 per non inseguire il rumore.

## 5. Ribilanciamento

- I pesi target ERC si **ricalcolano settimanalmente** (e si monitorano ogni giorno).
- Le **transazioni** si eseguono: ogni mese, oppure prima se un asset devia oltre **5%**
  dal suo peso target (trigger a soglia). Compromesso fra drift e costi di turnover.

## 6. Circuit breaker sul drawdown (forma di Tom, soglie di Chloe)

Riduzione continua dell'esposizione in funzione del drawdown dall'High Water Mark — funzione
lineare a tratti, niente salti bruschi:

- Drawdown < 8%: esposizione piena (100%).
- Drawdown 8% → 15%: esposizione scende linearmente da 100% verso il floor.
- Drawdown ≥ 15%: esposizione al **floor 30%** (solo blocco core). Non si azzera mai —
  uscire del tutto sarebbe una scommessa direzionale, esattamente ciò che il pivot ha escluso.
- **Rientro graduale**: l'esposizione risale al massimo del 2%/giorno e solo se il
  portafoglio non segna nuovi minimi. HWM non si resetta mai.

## 7. Filtro di regime (Chloe)

Reattivo, non predittivo — il motore reagisce a ciò che osserva, non anticipa:

- **Primario**: vol realizzata del *portafoglio* (non del VIX) — guida il vol targeting.
- **Secondario**: VIX spot. >30 → finestra vol più corta + soglia circuit breaker abbassata.
  >40 → "crisis mode": esposizione ≤50%, ribilanciamento sospeso (no trade in mercati illiquidi).
- **Terziario**: VIX term structure (backwardation VIX/VXV>1 = stress acuto) → soglia di
  riduzione esposizione più conservativa.

## 8. Costi da modellare nel backtest (Chloe)

Spread + slippage + commissioni per asset class (DJP il più caro: ~0.08% spread, 0.75%
expense ratio). **Costo totale stimato: 0.25-0.40%/anno** — da sottrarre al rendimento lordo.

## 9. Limiti onesti — cosa il motore NON fa

- **Non è un hedge.** Nel 2022 la correlazione equity-bond è passata da −0.3 a +0.7: TLT
  −31%, SPY −18% insieme. Un all-weather avrebbe perso 6-12%. Il motore *attenua*, non annulla.
- **Non batte SPY in un bull market prolungato.** Se il prossimo decennio somiglia agli
  anni 2010, un semplice SPY buy-and-hold farà meglio. Il motore vince nei bear market e
  nell'alta volatilità.
- **Non protegge da**: regime inflazionistico strutturale pluriennale, deflazione da debito
  (tutti i premi per il rischio si comprimono insieme), flash crash di liquidità, errori di
  esecuzione del software (→ paper trading E4 obbligatorio).
- Il premio per il rischio è un *compenso per il rischio*, non un pasto gratis: il motore
  riduce i drawdown, non li elimina.

## 10. Parametri — riepilogo

| Parametro | Valore | Fonte |
|-----------|--------|-------|
| Universo | 8 ETF (SPY VEA VWO TLT IEF TIP GLD DJP) | Chloe |
| Allocazione | ERC (Equal Risk Contribution) | Tom |
| Covarianza | Ledoit-Wolf, T=252, ricalcolo settimanale | Tom |
| Vol realizzata | EWMA λ=0.94 | Tom |
| **Vol target** | **12%/anno** (scelto dall'utente, 2026-05-22) | utente |
| Leva | Nessuna — scaling [0,1] | Max (vs Tom 2x) |
| Ribilanciamento | Pesi settimanali, transazioni mensili + soglia 5% | Chloe/Tom |
| Circuit breaker | Lineare a tratti, nodi 8%/15%, floor 30%, rientro 2%/gg | Tom/Chloe |
| Costo modellato | 0.25-0.40%/anno | Chloe |

## 11. Decisione dell'utente (2026-05-22)

**Vol target = 12%/anno** (profilo intermedio). Scelta di policy dell'utente: un po' più
di rendimento atteso rispetto al 10% conservativo di Chloe, con drawdown ancora gestibili.
Senza leva, il motore raggiunge il 12% concentrando un po' di più sugli asset volatili
nei periodi di bassa volatilità di mercato — diversificazione leggermente ridotta ma
accettabile. Parametro congelato per E2.
