# C003 Release Readiness Gate

Context: C003
Date: 2026-09-30
Status: ENGINE CANDIDATE
Milestone: 6

## Goal

Make stable-release readiness a deterministic, fail-closed evidence decision.

## Required gates

A stable Repository Intelligence release can be eligible for parent release review only when all of these gates are verified with evidence:

- C002 completion;
- live Codex runtime proof;
- live Claude Code runtime proof;
- live provider parity on the same revision and deterministic baseline;
- real failure/rollback proof;
- deterministic reproducibility pack;
- security;
- privacy;
- license;
- verifier.

In addition, the top-level open-blocker list must be empty.

## Decisions

### eligible-for-parent-release-review

Every mandatory gate is verified with evidence and no blocker remains.

This does not release anything automatically.

### blocked

At least one gate is blocked/pending, lacks evidence, contains a contradictory blocker, or the package has an open blocker.

## No automatic release

The evaluator always sets `auto_release=false`.

Even when every gate passes, the only machine decision is `eligible-for-parent-release-review`. Final release authority remains with the parent steward.

## Current C003 verdict

The current evidence package is intentionally BLOCKED because:

- Codex live runtime proof is blocked by OpenAI API quota;
- Claude Code live runtime proof is blocked because runtime authentication is not configured;
- live provider parity cannot be verified until both runtime proofs pass.

Milestones 3, 4, and 5 being verified does not override these missing live-runtime gates.

The gate engine may be verified independently while the stable release remains blocked.
