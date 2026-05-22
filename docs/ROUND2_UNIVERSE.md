# TradingIA — Round 2 Universe: Lista Congelata

> **Data di congelamento: 2026-05-21**
> Documento redatto da Chloe (Trader / Risk) — validato prima che Tom scarichi qualsiasi dato.
>
> **AVVISO PROTOCOLLO §13**: questa lista e' definita per ragioni economiche strutturali,
> prima di osservare i dati. Qualsiasi modifica ai ticker dopo il download iniziale di Tom
> **invalida il protocollo di validazione**. Se un ticker risulta mancante su yfinance al
> momento del download, la procedura corretta e' escluderlo e documentare l'esclusione —
> non sostituirlo con un alternativo scelto post-hoc.
>
> Tutti i ticker sono stati scelti con criterio point-in-time: devono esistere su yfinance
> almeno dal 2010-01-01 per coprire il periodo IS senza survivorship bias.

---

## Universo A — MOMENTUM CROSS-SECTIONAL (42 ETF)

**Razionale generale**: paniere diversificato per costruire ranking cross-sectional robusto.
La diversificazione tra asset class e' fondamentale: un paniere monotematico (es. solo
settoriali USA) concentra il rischio di regime e genera segnali correlati che gonfiano
lo Sharpe apparente.

---

### Gruppo 1 — Settoriali USA (XL*) — 11 ticker

Copertura completa dell'S&P 500 per settore GICS. Disponibili dal 1998-1999 su yfinance.
Sono il benchmark classico del momentum settoriale: 11 settori ortogonali con rotazione
ciclica ben documentata in letteratura (Moskowitz & Grinblatt 1999).

| Ticker | Nome esteso |
|--------|-------------|
| XLK | Technology Select Sector SPDR Fund |
| XLV | Health Care Select Sector SPDR Fund |
| XLF | Financial Select Sector SPDR Fund |
| XLE | Energy Select Sector SPDR Fund |
| XLI | Industrial Select Sector SPDR Fund |
| XLY | Consumer Discretionary Select Sector SPDR Fund |
| XLP | Consumer Staples Select Sector SPDR Fund |
| XLB | Materials Select Sector SPDR Fund |
| XLU | Utilities Select Sector SPDR Fund |
| XLRE | Real Estate Select Sector SPDR Fund (*) |
| XLC | Communication Services Select Sector SPDR Fund (*) |

(*) XLRE (2015) e XLC (2018) sono piu' recenti: disponibili solo per il periodo OOS e parte
della VAL. Inclusi per completezza settoriale ma la finestra IS deve usare 9 settori.
Tom: usare storia disponibile reale, non imputare dati mancanti.

---

### Gruppo 2 — Equity Internazionale e Mercati Emergenti — 8 ticker

Cattura momentum geografico e di regione. Disponibili tutti dal 2003-2007 su yfinance.
Il momentum geografico ha persistenza documentata su dati mensili (Asness, Moskowitz,
Pedersen 2013) ed e' decorrelato dal momentum settoriale USA in regime di stress.

| Ticker | Nome esteso |
|--------|-------------|
| EFA | iShares MSCI EAFE ETF (Europa, Australasia, Far East) |
| EEM | iShares MSCI Emerging Markets ETF |
| VGK | Vanguard FTSE Europe ETF |
| EWJ | iShares MSCI Japan ETF |
| FXI | iShares China Large-Cap ETF |
| EWZ | iShares MSCI Brazil ETF |
| ILF | iShares Latin America 40 ETF |
| INDA | iShares MSCI India ETF |

---

### Gruppo 3 — Fixed Income — 7 ticker

Duration diversa (breve, medio, lungo termine) e credito diverso (gov, IG, HY).
Il momentum su bond e' piu' lento ma documentato su timeframe mensile. Fondamentale
per la diversificazione del portafoglio in regime risk-off — evita il long-only equity bias.

| Ticker | Nome esteso |
|--------|-------------|
| SHY | iShares 1-3 Year Treasury Bond ETF |
| IEF | iShares 7-10 Year Treasury Bond ETF |
| TLT | iShares 20+ Year Treasury Bond ETF |
| LQD | iShares iBoxx $ Investment Grade Corporate Bond ETF |
| HYG | iShares iBoxx $ High Yield Corporate Bond ETF |
| EMB | iShares JP Morgan USD Emerging Markets Bond ETF |
| TIP | iShares TIPS Bond ETF (inflazione) |

---

### Gruppo 4 — Commodity — 6 ticker

Copertura multi-commodity via ETF liquidi. Il momentum sulle commodity e' piu' ciclico
(legato a cicli di inventario e domanda fisica). Importante per decorrelazione con equity
in periodi inflazionistici.

| Ticker | Nome esteso |
|--------|-------------|
| GLD | SPDR Gold Shares |
| SLV | iShares Silver Trust |
| USO | United States Oil Fund LP |
| UNG | United States Natural Gas Fund LP |
| DBA | Invesco DB Agriculture Fund |
| DBB | Invesco DB Base Metals Fund |

Avviso: USO e UNG hanno roll cost implicito (future in contango) che riduce il rendimento
rispetto allo spot. Il backtest con questi ETF sottostima il rendimento della commodity
fisica ma rappresenta il veicolo tradabile reale — corretto per i nostri scopi.

---

### Gruppo 5 — REIT — 4 ticker

Esposizione immobiliare diversificata. I REIT hanno momentum ciclico legato ai tassi di
interesse e sono parzialmente decorrelati dall'equity industriale. Includono sia REIT
domestici che internazionali per varieta' geografica.

| Ticker | Nome esteso |
|--------|-------------|
| VNQ | Vanguard Real Estate ETF |
| IYR | iShares U.S. Real Estate ETF |
| REM | iShares Mortgage Real Estate ETF |
| VNQI | Vanguard Global ex-U.S. Real Estate ETF |

---

### Gruppo 6 — Valute via ETF — 3 ticker

Esposizione valutaria tramite ETF (non forex diretto): evita il financing overnight tipico
del forex e consente il confronto apple-to-apple nel ranking cross-sectional. I 3 ETF
coprono valute rifugio (JPY, CHF) e dollar-proxy (UUP).

| Ticker | Nome esteso |
|--------|-------------|
| UUP | Invesco DB US Dollar Index Bullish Fund |
| FXY | Invesco CurrencyShares Japanese Yen Trust |
| FXF | Invesco CurrencyShares Swiss Franc Trust |

Nota: FXE (Euro) e FXB (GBP) esclusi perche' molto correlati a UUP inverso — aggiungono
poco al ranking ma aumentano la correlazione interna al gruppo. 3 ticker sono sufficienti
per catturare il segnale valutario nel ranking.

---

### Gruppo 7 — Volatilita' e Factor ETF — 3 ticker

Fattori alternativi (value, quality, low-vol) per catturare premi al rischio non correlati
al momentum puro. La volatilita' (VIXY) agisce come hedge naturale in regime di stress —
quando il ranking la porta in top quantile, segnala regime difensivo.

| Ticker | Nome esteso |
|--------|-------------|
| VIXY | ProShares VIX Short-Term Futures ETF |
| QUAL | iShares MSCI USA Quality Factor ETF |
| USMV | iShares MSCI USA Min Vol Factor ETF |

Avviso VIXY: ETF su future VIX con roll cost molto alto (20-30% annuo di decadimento
in contango). Il momentum su VIXY funziona solo in momentum positivo di breve durata —
holding prolungato e' distruttivo. Il ranking cross-sectional lo gestisce naturalmente
perche' in periodi normali sara' in bottom quantile (corto o flat).

---

### Riepilogo Universo MOMENTUM

| Gruppo | Ticker | N |
|--------|--------|---|
| 1 — Settoriali USA XL* | XLK, XLV, XLF, XLE, XLI, XLY, XLP, XLB, XLU, XLRE, XLC | 11 |
| 2 — Equity Internazionale/EM | EFA, EEM, VGK, EWJ, FXI, EWZ, ILF, INDA | 8 |
| 3 — Fixed Income | SHY, IEF, TLT, LQD, HYG, EMB, TIP | 7 |
| 4 — Commodity | GLD, SLV, USO, UNG, DBA, DBB | 6 |
| 5 — REIT | VNQ, IYR, REM, VNQI | 4 |
| 6 — Valute ETF | UUP, FXY, FXF | 3 |
| 7 — Volatilita'/Factor | VIXY, QUAL, USMV | 3 |
| **TOTALE** | | **42** |

---

## Universo B — PAIRS TRADING (14 coppie)

**Razionale generale**: coppie selezionate per legame economico strutturale pre-esistente,
non per correlazione storica osservata. Seguendo §13 del protocollo: la selezione e' fatta
per ragioni fondamentali, il test di cointegrazione verra' eseguito su IS soltanto da Tom,
con correzione FDR Benjamini-Hochberg e SPA per il candidato selezionato.

Segnalazione rischio strutturale: alcune coppie sono soggette a rottura strutturale
prevedibile. Queste sono marcate con [RISCHIO ROTTURA].

---

### Categoria I — Doppio Provider, Stessa Esposizione (4 coppie)

Due ETF diversi che replicano lo stesso benchmark: il legame economico e' la replica
identica dell'indice sottostante. Lo spread e' quasi puro costo di frizione (expense ratio,
liquidita', creation/redemption). La cointegrazione qui e' quasi certa — il rischio e'
che il pair sia troppo stretto per generare segnali tradabili (spread troppo piccolo).

| Coppia | Ticker A | Ticker B | Legame economico strutturale |
|--------|----------|----------|------------------------------|
| I-1 | SPY | IVV | Entrambi replicano S&P 500 (SPDR vs iShares). Expense ratio 0.0945% vs 0.03% — spread residuo da tracking difference e liquidita' intraday. |
| I-2 | QQQ | QQQM | Entrambi replicano Nasdaq-100 (versione istituzionale vs retail di Invesco). QQQM dal 2020 — finestra IS ridotta. |
| I-3 | GLD | IAU | Entrambi replicano oro fisico (SPDR vs iShares). IAU ha expense ratio piu' basso (0.25% vs 0.40%) — spread medio ~5-10bps. |
| I-4 | EFA | VEA | Entrambi replicano MSCI EAFE (iShares vs Vanguard). Differenza metodologica minima. |

[RISCHIO ROTTURA I-2]: QQQM ha storia corta (2020). Se la storia IS non e' sufficiente,
questa coppia va esclusa automaticamente senza sostituzione.

---

### Categoria II — Competitor Diretti, Stesso Settore (4 coppie)

Aziende che competono nello stesso mercato: i loro fondamentali si muovono insieme
nel lungo termine (stesso ciclo di domanda, stessa regolamentazione, stesse macro forze)
ma divergono nel breve termine per notizie idiosincratiche. Il mean-reversion e' giustificato
dal fatto che la quota di mercato non puo' spostarsi indefinitamente senza riadattamento.

| Coppia | Ticker A | Ticker B | Legame economico strutturale |
|--------|----------|----------|------------------------------|
| II-1 | XOM | CVX | ExxonMobil vs Chevron: i due maggiori oil major integrati USA. Stesso ciclo del petrolio, stessa regolamentazione. Spread guidato da differenze nella qualita' degli asset e allocazione del capitale. |
| II-2 | JPM | BAC | JPMorgan Chase vs Bank of America: le due maggiori banche USA per asset. Stesso ciclo creditizio, stessa regolamentazione Fed. Spread guidato da esposizione geografica e mix di business. |
| II-3 | MSFT | GOOGL | Microsoft vs Alphabet: i due maggiori player cloud/enterprise (Azure vs GCP) + AI infrastruttura. Ciclo tecnologico comune, spread guidato da mix di ricavi (enterprise vs advertising). |
| II-4 | KO | PEP | Coca-Cola vs PepsiCo: duopolio bevande. Correlazione fondamentale altissima da 70 anni. Spread guidato da esposizione snack (PEP piu' diversificata con Frito-Lay). |

[RISCHIO ROTTURA II-3]: MSFT/GOOGL puo' perdere cointegrazione se uno dei due domina
il mercato AI in modo strutturalmente irreversibile. Half-life da monitorare rolling.

---

### Categoria III — Settoriali Complementari (3 coppie)

ETF settoriali con relazione economica di complementarita' o sostituzione: non competono
direttamente ma sono guidati da fattori macro comuni con divergenze settoriali prevedibili.

| Coppia | Ticker A | Ticker B | Legame economico strutturale |
|--------|----------|----------|------------------------------|
| III-1 | XLF | XLU | Finanziari vs Utilities: entrambi sensibili ai tassi di interesse ma in direzione opposta (XLF beneficia da tassi alti, XLU soffre). Lo spread e' un proxy del ciclo dei tassi — mean-reverting nel lungo termine perche' i tassi sono ciclici. |
| III-2 | XLE | XLB | Energy vs Materials: entrambi commodity-driven. L'energia (petrolio) e i materiali (metalli, chimica) condividono il ciclo economico globale e la domanda dei mercati emergenti. |
| III-3 | XLY | XLP | Consumer Discretionary vs Consumer Staples: il classico pair ciclico/difensivo. La rotazione tra i due e' guidata dal ciclo economico — mean-reverting nel lungo termine perche' il ciclo economico e' ciclico per definizione. |

---

### Categoria IV — Macro Cross-Asset (3 coppie)

Coppie tra asset class diverse legate da relazioni macro strutturali. Il legame e' piu'
lento (mesi, non giorni) e la cointegrazione e' meno certa — ma quando esiste, il
segnale e' economicamente robusto e poco affollato.

| Coppia | Ticker A | Ticker B | Legame economico strutturale |
|--------|----------|----------|------------------------------|
| IV-1 | TLT | GLD | Treasury a lungo termine vs Oro: entrambi asset rifugio. Il legame e' il tasso reale USA — tassi reali bassi = gold outperform, tassi reali alti = treasury outperform. Mean-reverting intorno al regime dei tassi reali. |
| IV-2 | EEM | GLD | Mercati Emergenti vs Oro: l'EM beneficia dalla crescita globale e dal dollaro debole; l'oro beneficia dal dollaro debole e dall'inflazione. Il driver comune (dollaro) crea un legame strutturale parziale. |
| IV-3 | HYG | SPY | High Yield Bond vs S&P 500: entrambi sensibili al risk appetite. Il credit spread HY e' un leading indicator del mercato azionario — cointegrazione di lungo termine documentata. |

[RISCHIO ROTTURA IV-1]: TLT/GLD puo' perdere cointegrazione in regimi di stagflazione
dove entrambi salgono o in regimi di deflazione dove entrambi scendono. La relazione e'
condizionale al regime di tassi reali — da monitorare con rolling ADF sui residui.

[RISCHIO ROTTURA IV-2]: EEM/GLD ha cointegrazione piu' debole delle altre coppie —
il legame via dollaro e' mediato e puo' rompersi in regimi di risk-off estremo dove l'oro
sale e l'EM crolla simultaneamente. Candidato a essere eliminato dopo FDR.

[RISCHIO ROTTURA IV-3]: HYG/SPY — la cointegrazione regge in regime normale ma si rompe
durante stress acuti di credito (2008, 2020) dove HYG scende piu' di SPY per illiquidita'
del mercato HY. Half-life da monitorare: se supera 60 giorni il pair non e' tradable.

---

### Riepilogo Universo PAIRS

| Categoria | Coppie | N |
|-----------|--------|---|
| I — Doppio provider | SPY/IVV, QQQ/QQQM, GLD/IAU, EFA/VEA | 4 |
| II — Competitor diretti | XOM/CVX, JPM/BAC, MSFT/GOOGL, KO/PEP | 4 |
| III — Settoriali complementari | XLF/XLU, XLE/XLB, XLY/XLP | 3 |
| IV — Macro cross-asset | TLT/GLD, EEM/GLD, HYG/SPY | 3 |
| **TOTALE** | | **14 coppie / 25 ticker unici** |

---

## Costi di Trading per Asset Class (VALIDATION_PROTOCOL §7)

Questi costi DEVONO essere inclusi nel backtest. Omettere anche un solo componente
costituisce violazione del §7 e attiva il Killer Criterion K5.

### ETF azionari USA liquidi (XL*, SPY, QQQ, IVV, VEA, EFA)

| Componente | Stima conservativa | Note |
|------------|-------------------|------|
| Spread bid/ask | 0.01-0.03% | ETF molto liquidi, spread minimo |
| Commissioni broker | 0.00-0.05% | Dipende dal broker; Interactive Brokers ~$0.005/share |
| Slippage esecuzione | 0.02-0.05% | Market order su ETF liquidi |
| Borrow cost (short) | 0.25-0.50% annuo | ETF mainstream, borrow facile |
| **Round-trip totale** | **0.10-0.20%** | Per rotazione mensile: ~1.2-2.4% annuo |

### ETF commodity (GLD, SLV, GLD, IAU, USO, UNG, DBA, DBB)

| Componente | Stima conservativa | Note |
|------------|-------------------|------|
| Spread bid/ask | 0.03-0.10% | Piu' ampio per ETF meno liquidi (UNG, DBA) |
| Commissioni broker | 0.00-0.05% | Come sopra |
| Slippage esecuzione | 0.05-0.15% | Piu' alto per ETF su commodity meno liquide |
| Roll cost implicito | 0.05-0.15%/mese | Solo USO, UNG, DBA: contango dei future sottostanti |
| Borrow cost (short) | 0.50-2.00% annuo | Piu' alto per commodity ETF |
| **Round-trip totale** | **0.20-0.50%** | Piu' alto per commodity con roll cost |

### ETF Fixed Income (SHY, IEF, TLT, LQD, HYG, EMB, TIP)

| Componente | Stima conservativa | Note |
|------------|-------------------|------|
| Spread bid/ask | 0.02-0.08% | HYG e EMB piu' ampi (mercato bond meno liquido) |
| Commissioni broker | 0.00-0.05% | Come sopra |
| Slippage esecuzione | 0.03-0.10% | Piu' alto per bond ETF |
| Borrow cost (short) | 0.25-1.00% annuo | HYG e EMB piu' costosi da shortare |
| **Round-trip totale** | **0.10-0.30%** | Piu' alto per HY e EM bond |

### ETF internazionali / EM (EEM, VGK, EWJ, FXI, EWZ, ILF, INDA, VNQI)

| Componente | Stima conservativa | Note |
|------------|-------------------|------|
| Spread bid/ask | 0.05-0.15% | EM e single-country piu' ampi |
| Commissioni broker | 0.05-0.10% | Spesso piu' caro per mercati esteri |
| Slippage esecuzione | 0.05-0.20% | Bassa liquidita' intraday su single-country ETF |
| Borrow cost (short) | 0.50-3.00% annuo | EWZ, FXI, ILF: borrow difficile e costoso |
| **Round-trip totale** | **0.20-0.50%** | Piu' alto per single-country EM |

### ETF valute e volatilita' (UUP, FXY, FXF, VIXY)

| Componente | Stima conservativa | Note |
|------------|-------------------|------|
| Spread bid/ask | 0.05-0.10% | Meno liquidi degli ETF azionari |
| Slippage esecuzione | 0.05-0.15% | Volumi piu' bassi |
| Roll cost VIXY | 15-25% annuo | Decadimento strutturale da contango VIX future |
| Borrow cost (short) | 0.50-2.00% annuo | |
| **Round-trip totale** | **0.20-0.40%** (escluso roll VIXY) | VIXY e' tenuto solo in momentum positivo |

### Coppie — Costo aggiuntivo per struttura Long/Short

Per le strategie pairs, il costo e' la **somma** di entrambe le gambe piu' il financing:

| Componente | Stima |
|------------|-------|
| Somma spread bid/ask (2 gambe) | 0.10-0.40% |
| Financing overnight (margin/CFD) | ~3% annuo = 0.008%/giorno = ~0.12% per holding 15gg |
| Borrow cost gamba short | 0.25-3.00% annuo (dipende dal ticker) |
| **Costo pairs round-trip tipico** | **0.30-0.80%** per trade (holding ~15gg) |

**Soglia di sopravvivenza (dal §7)**: il momentum lordo deve generare almeno 3x i costi.
Con round-trip ETF ~0.15% (media pesata sul paniere) e rotazione mensile:
- Costo annuo: ~1.8% (12 rotazioni x 0.15%)
- Soglia minima momentum lordo: **1.8%/mese** per superare il killer criterion K5.

Per i pairs: con costo round-trip ~0.50% e holding medio 15 giorni:
- ~2 trade/mese per coppia attiva
- Costo mensile per coppia: ~1.00%
- Soglia minima mean-reversion lordo: **3.0%/trade** per sopravvivere dopo costi.

---

## Note operative per Tom

1. **Data di inizio download**: 2010-01-01 come minimo. Per XLRE e XLC usare data reale di IPO.
2. **Frequenza dati**: giornaliera (daily close adjusted) per il momentum; daily per i pairs.
3. **Adjusted close**: usare SEMPRE `auto_adjust=True` in yfinance per gestire split e dividendi.
4. **Ticker da verificare su yfinance prima di scaricare**: QQQM (IPO 2020), INDA (IPO 2012),
   VNQI (IPO 2010), ILF (verificare liquidita' pre-2010), REM (verificare storia).
5. **Se un ticker fallisce il download**: escluderlo e documentare — NON sostituire.
6. **Ticker potenzialmente problematici**: UNG e USO hanno avuto reverse split multipli —
   verificare che yfinance restituisca serie adjusted corrette prima di procedere.
