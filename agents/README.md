# Agenti AI del Progetto TradingIA

Sistema **a due livelli** per gestire gli agenti specializzati di TradingIA:

```
.claude/agents/<nome>.md   ← definizione subagent (frontmatter + workflow)
agents/<nome>.md           ← specifica narrativa (identità, stile, expertise) — riferimento per l'utente
agents/memory/<nome>.md    ← memoria operativa persistente (auto-aggiornata)
```

---

## Agenti attivi

| Nome | Modello | Ruolo | Quando usarlo |
|------|---------|-------|---------------|
| **Max** | **Opus** | Coordinatore strategico, ingegnere finanziario, consulente | Sempre. È l'unica interfaccia con l'utente |
| **Paky** | Sonnet | Ingegnere del Software | Implementazioni, refactoring, fix bug, GUI wiring |
| **Tom** | Sonnet | Matematico / ML | Derivazioni, algoritmi, modelli AI, statistica |
| **Chloe** | Sonnet | Trader istituzionale / Risk | Validazione strategie, risk assessment, mercati reali |
| **Marco** | Sonnet | GUI / Grafica / Data Viz | Rendering, theming, info widgets, charting |

Max è su Opus per la visione integrata e i consigli strategici (alto valore decisionale). Gli altri sono Sonnet (specializzati, ripetitivi, costi inferiori).

---

## Architettura del sistema

### 1. Definizione subagent — `.claude/agents/<nome>.md`

File con frontmatter YAML che dichiara il subagent invocabile via `Agent(subagent_type="<nome>", ...)`.

```yaml
---
name: paky
description: Ingegnere software senior...
model: sonnet
---
# corpo del prompt: identità, stile, workflow memoria, expertise
```

Max li invoca quando delega un task specifico. L'utente NON chiama mai direttamente questi subagent: tutto passa per Max.

### 2. Memoria operativa — `agents/memory/<nome>.md`

Ogni agente ha un file Markdown versionato in git con:
- **Decisioni recenti** (max 20, FIFO): cosa ha fatto nelle ultime sessioni
- **Lezioni apprese** (permanenti): insidie/principi scoperti, non più dimenticati
- **Task aperti**: a cosa stava lavorando
- Sezioni specifiche per ruolo:
  - Max: "Consigli dati all'utente"
  - Paky: "Pattern di codice scoperti"
  - Tom: "Modelli e parametri ottimali noti"
  - Marco: "Pattern di rendering scoperti"
  - Chloe: "Domande critiche da farsi sempre"

**Workflow obbligatorio per ogni agente:**
1. **All'inizio del task**: leggi `agents/memory/<nome>.md` per recuperare contesto
2. **Alla fine del task**: aggiungi 1-3 righe sotto "Decisioni recenti" + aggiorna sezioni se hai imparato qualcosa di nuovo

Questo dà continuità tra sessioni: l'agente non riparte mai da zero, ricorda cosa ha già fatto e cosa ha imparato.

### 3. Specifica narrativa — `agents/<nome>.md`

File originale di "personalità" dell'agente. Letto dall'utente per capire chi fa cosa. Il contenuto sostanziale è duplicato nel subagent in `.claude/agents/<nome>.md` (Claude Code non supporta transclude tra file Markdown).

---

## Come usarli

**L'utente parla solo con Max.** Non chiama gli altri agenti direttamente — è Max che decide e delega via `Agent(subagent_type="...")`.

```
Utente: "Max, ho bisogno di rifare la GUI"
Max:    "[Max] Coinvolgo Marco per il design e Paky per l'implementazione..."
        (delega internamente, riporta risultato unificato)
Utente: "Max, ecco il risultato della tua proposta"
```

---

## Come creare un nuovo agente

1. Crea il file di specifica narrativa: `agents/<nome>.md` (identità, stile, expertise, file di competenza)
2. Crea il subagent: `.claude/agents/<nome>.md` con frontmatter:
   ```yaml
   ---
   name: <nome>
   description: <quando usarlo>
   model: sonnet  # o opus per ruoli strategici
   ---
   # corpo del prompt (può duplicare/riassumere agents/<nome>.md)
   # IMPORTANTE: include sezione "Workflow obbligatorio" con read/write su agents/memory/<nome>.md
   ```
3. Crea il file memoria: `agents/memory/<nome>.md` con le sezioni standard (Decisioni recenti, Lezioni apprese, Task aperti)
4. Aggiorna questo README e la tabella in `CLAUDE.md` se serve
5. Aggiorna `.claude/agents/max.md` aggiungendo l'agente nella tabella "Il team che coordini"

---

## Agenti suggeriti per il futuro

| Nome | Ruolo possibile | Modello |
|------|----------------|---------|
| **Alex** | DevOps / Deployment / Docker / CI-CD | Sonnet |
| **Nina** | QA Engineer / Testing / Debug strutturato | Sonnet |
| **Sara** | Data Engineer / Pipeline dati / ETL | Sonnet |
