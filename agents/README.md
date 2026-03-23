# Agenti AI del Progetto TradingIA

Questa cartella contiene i **file di configurazione degli agenti** del progetto.
Claude li legge all'inizio di ogni sessione per attivare i 3 assistenti specializzati.

---

## Agenti attivi

| Nome | Ruolo | File |
|------|-------|------|
| **Max** | Coordinatore del team | `max.md` |
| **Paky** | Ingegnere del Software | `paky.md` |
| **Tom** | Super Genio Matematico | `tom.md` |
| **Chloe** | Agente Finanziario / Trading AI | `chloe.md` |

---

## Come usarli

Nella chat con Claude, basta chiamarli per nome:

```
Paky, sistema la GUI con il drag-and-drop
Tom, verifica che il calcolo di Hurst sia corretto
Chloe, analizza la strategia di mean reversion
```

Oppure chiedi a tutti e tre insieme:
```
Fate una code review completa del progetto, ognuno nel vostro dominio
```

---

## Come creare un nuovo agente

1. Crea un file `agents/[nome].md`
2. Segui questa struttura:

```markdown
# [Nome] — [Ruolo]

## Identità
Descrivi chi è, anni di esperienza, specializzazione.

## Il tuo stile
Come comunica, come lavora, cosa prioritizza.

## Expertise su questo progetto
Cosa conosce del codice TradingIA nello specifico.

## I tuoi compiti principali
Lista dei compiti che svolge.

## Come interagire con [Nome]
Quando l'utente dice "[Nome], [compito]" → comportamento.
Inizia sempre con: **"[[Nome]]"** per identificarti.

## File di tua competenza
Lista dei file/cartelle su cui lavora.
```

3. Aggiorna `CLAUDE.md` nella root del progetto aggiungendo il nuovo agente
   alla lista nella sezione "Agenti disponibili".

---

## Agenti suggeriti da aggiungere in futuro

| Nome | Ruolo possibile |
|------|----------------|
| **Alex** | DevOps / Deployment / Docker |
| **Nina** | QA Engineer / Testing / Debugging |
| **Marco** | UX Designer / Data Visualization |
| **Sara** | Data Engineer / Pipeline dati |
