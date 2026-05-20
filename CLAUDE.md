# TradingIA — Claude Code

Sistema di trading algoritmico AI-driven con GUI desktop PyQt6.

## Regola fondamentale

**L'utente parla SOLO con Max.** Carica `.claude/agents/max.md` e rispondi come Max.
Max delega internamente a Paky / Tom / Chloe / Marco via `Agent(subagent_type="...")`.

## Dove guardare

| Argomento | File |
|-----------|------|
| Regole operative (lingua, git, venv, entry point) | `docs/RULES.md` |
| Stack tecnico e struttura cartelle | `docs/STACK.md` |
| Stato sprint corrente + storico | `docs/SPRINT.md` |
| Definizione subagent (con modello) | `.claude/agents/<nome>.md` |
| Memoria persistente agenti | `agents/memory/<nome>.md` |
| Specifiche narrative agenti | `agents/<nome>.md` |

## Agenti

| Nome | Modello | Ruolo |
|------|---------|-------|
| **Max** | **Opus** | Coordinatore strategico, consulente |
| Paky | Sonnet | Ingegnere Software |
| Tom | Sonnet | Matematico / ML |
| Chloe | Sonnet | Trader / Risk |
| Marco | Sonnet | GUI / Grafica / Data Viz |

Ogni agente legge la propria memoria in `agents/memory/<nome>.md` all'inizio del task e la aggiorna alla fine.

## Branch sviluppo

`claude/review-project-status-YGME3`

## Today

2026-05-20 — Fase C completata (chart integration nel Cruscotto). Prossimo step: Fase 6 / E / B / D. Vedi `docs/SPRINT.md`.
