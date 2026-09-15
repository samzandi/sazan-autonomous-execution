# Execution Model

## States

### INTAKE
Define final goal, constraints, available context, evidence standard, and consequential boundaries.

### PLAN
Create an ordered dependency-aware task graph. Prefer executable units with clear verification criteria.

### EXECUTE
Perform the highest-priority unblocked safe action.

### VERIFY
Check that the intended outcome exists and is correct. Prefer direct evidence: re-fetch written files, run tests/builds, inspect status, compare expected vs actual, or query the authoritative system.

### RECOVER
When verification fails, diagnose and repair. A failure is not automatically a human blocker.

### CONTINUE
Update task state and immediately choose the next unblocked action. Do not emit a progress-only response when more executable work can be completed in the same active run.

### ESCALATE
Ask the human only for the minimum missing credential, access, approval, evidence, or owner decision needed to unblock progress.

### COMPLETE
Confirm goal coverage, validation evidence, remaining risks, and precise completion status.

## Transition rules

- INTAKE → PLAN when the end goal is sufficiently clear.
- PLAN → EXECUTE when at least one safe action is available.
- EXECUTE → VERIFY after every material action.
- VERIFY → CONTINUE on success.
- VERIFY → RECOVER on a recoverable failure.
- RECOVER → VERIFY after remediation.
- Any state → ESCALATE only when a defined human blocker exists.
- CONTINUE → EXECUTE while work remains.
- CONTINUE → COMPLETE only when acceptance criteria are satisfied or remaining items are explicitly out of scope.

## Invariant

The existence of another safe, available, goal-relevant action means the workflow is not complete.
