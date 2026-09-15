# AGENTS.md

Read `SKILL.md` before executing repository tasks.

## Contract

- Work toward the final goal, not merely the current substep.
- Continue automatically while safe executable work remains.
- Verify important outputs after writes/actions.
- Recover from ordinary errors without handing the workflow back to the user prematurely.
- Escalate only under the stop conditions in `SKILL.md` and `docs/stop-conditions.md`.
- Never claim production-ready without evidence.
- Keep unrelated skills and projects separate unless an explicit integration has a technical reason.

## Default behavior

If the next action is obvious, safe, reversible, and within granted access, execute it rather than asking whether to continue.
