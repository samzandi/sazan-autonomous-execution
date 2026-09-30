# C003 Failure and Rollback Evidence

Context: C003
Date: 2026-09-30
Status: CANDIDATE
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

Status remains CANDIDATE until the pull-request lab and repository regressions pass.
