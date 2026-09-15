# Sazan Autonomous Execution

A platform-independent execution-control skill for AI agents that plans, executes, validates, recovers, documents, and continues until completion or a genuine human decision is required.

## Core principle

Do not stop just because a substep finished. Continue through every safe and available next action.

## State machine

`INTAKE → PLAN → EXECUTE → VERIFY → RECOVER → CONTINUE → COMPLETE`

Use `ESCALATE` only for genuine human-required blockers.

## Repository structure

- `SKILL.md` — reusable execution policy
- `AGENTS.md` — repository-level agent instructions
- `docs/execution-model.md` — state machine and control flow
- `docs/stop-conditions.md` — precise escalation rules
- `docs/evidence-and-validation.md` — evidence gates and completion semantics
- `templates/task-state.md` — persistent task-state template
- `templates/final-report.md` — completion report template

## Status

Initial implementation. No production-ready claim without validation evidence.
