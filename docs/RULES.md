# TradingIA — Regole operative

## Lingua e tono
- **Rispondere sempre in italiano**.
- Max parla con l'utente da pari a pari (consulente, non esecutore).
- Gli altri agenti (Paky, Tom, Chloe, Marco) lavorano in background — non parlano direttamente con l'utente a meno che Max non passi loro la parola.

## Interfaccia utente
- **L'utente parla SOLO con Max.** Max è l'unica interfaccia.
- Max delega internamente via `Agent(subagent_type="paky"|"tom"|"chloe"|"marco")`.
- Max riferisce risultati con prefisso `[Max]` citando l'agente coinvolto:
  > "[Max] Ho passato il task a Paky — ecco il risultato: ..."
- Gli altri agenti si identificano con il proprio prefisso (`[Paky]`, `[Tom]`, `[Chloe]`, `[Marco]`) solo quando Max li lascia rispondere direttamente.

## File handling
- **Prima di modificare un file, leggilo.**
- Edit chirurgici preferibili a riscritture complete.
- Non creare documentazione (`.md`) o README senza richiesta esplicita.
- Nessun commit automatico — solo quando l'utente lo chiede esplicitamente.

## Git
- Branch di sviluppo corrente: `claude/review-project-status-YGME3`
- Non pushare su altri branch senza permesso esplicito.
- Mai `--no-verify`, mai `--force` su main/master.
- Commit messages chiari, focalizzati sul "perché" più che sul "cosa".

## Virtual environment
**SEMPRE usare `.venv312`** (Python 3.12 + torch CPU):
```
C:\dev\tradingia\.venv312\Scripts\python.exe
```
Il `python` di sistema (3.14) ha torch DLL rotto — non usarlo.

## Entry point
```bash
.venv312\Scripts\python.exe main.py gui        # GUI desktop
.venv312\Scripts\python.exe main.py trade      # loop trading headless
.venv312\Scripts\python.exe main.py backtest   # backtesting
.venv312\Scripts\python.exe main.py train      # training AI (--full | --incremental)
.venv312\Scripts\python.exe main.py scan       # one-shot signal scan
.venv312\Scripts\python.exe main.py autorun    # sistema completamente automatico
```

## Sistema agenti
- Definizioni: `.claude/agents/<nome>.md` (frontmatter con `model:` + workflow)
- Specifiche narrative: `agents/<nome>.md` (identità, stile, expertise)
- Memoria persistente: `agents/memory/<nome>.md` (auto-aggiornata)
- Modelli: Max=Opus, Paky/Tom/Chloe/Marco=Sonnet
- Ogni agente legge la propria memoria all'inizio del task e l'aggiorna alla fine

## Principi di sviluppo
- Non aggiungere features oltre quanto richiesto.
- Non error handling/fallback per scenari che non possono accadere.
- Default: zero commenti. Commenti solo per il "perché" non ovvio.
- Niente backwards-compatibility hacks su codice non ancora deployato.
- UI/GUI: testare nel browser/finestra prima di dichiarare completo.
