# C003 Failure and Rollback Evidence

Context: C003
Date: 2026-09-30
Status: VERIFIED / PROMOTED
Milestone: 4

## Goal

Prove rollback as an executed, reproducible transaction rather than a declared status.

## Required transaction evidence

A verified rollback receipt must contain:

- an isolated `git-worktree` execution boundary;
- a verified rollback revision and tree hash;
- a distinct mutation revision;
- an observed post-mutation failure with non-zero exit code;
- the exact rollback target and an allowed rollback mechanism;
- post-rollback revision equality;
- post-rollback tree-hash equality;
- a clean candidate worktree;
- an unchanged parent workspace;
- a passing post-rollback functional validation;
- private-data compliance;
- no persisted secret markers or absolute execution paths.

## Real execution lab

The lab creates a real temporary Git repository, commits a verified baseline, creates an isolated candidate worktree, commits an intentionally breaking semantic change, observes a failing functional assertion, resets the candidate worktree to the verified rollback revision, and proves exact revision/tree restoration plus functional recovery.

No production repository is mutated by the lab.

## Promotion hardening

The C003 change also closes a policy gap: `checks.rollback.status = verified` is no longer sufficient by itself. A verified rollback gate must also include non-empty evidence.

Status: VERIFIED / PROMOTED.

## Verification evidence

- initial lab run 36768911269 correctly blocked because Python functional checks created an untracked __pycache__ directory, proving the clean-worktree gate was effective;
- functional checks were hardened with Python -B to prevent bytecode side effects;
- verified lab run 36769117578 passed all rollback contract tests;
- promotion-gate regression tests passed;
- the real failure and rollback transaction passed;
- final revision and tree hash exactly matched the verified rollback point;
- candidate worktree was clean;
- parent workspace remained unchanged;
- functional validation passed after rollback;
- all repository regression workflows passed.
