# Sazan Repository Intelligence — C003 Index

Context: C003
Date: 2026-09-30
Status: ACTIVE
Topic: Runtime Proof and Release Readiness

## Objective

Prove that the promoted C002 Repository Intelligence pipeline behaves correctly in live coding-agent runtimes, preserve the same evidence and safety contracts across providers, and prepare the system for a stable release candidate.

## Initial scope

- live Codex runtime proof;
- live Claude Code runtime proof;
- runtime/provider contract parity;
- failure and rollback evidence under real execution;
- reproducibility pack for the C002 end-to-end pipeline;
- release-readiness checklist and evidence gate;
- stable release candidate preparation after runtime proof.

## Milestone 1 — Codex runtime proof

Goal:
- execute the promoted Repository Intelligence flow through an authorized Codex runtime;
- capture repository revision, runtime/provider version, route selection, budget receipts, artifacts, verifier decision, and rollback evidence;
- confirm that the final state cannot bypass parent review;
- confirm private identity redaction in persisted evidence;
- compare the live result against the deterministic C002 lab baseline.

Required terminal state:
- VERIFIED with reproducible evidence, or
- BLOCKED with explicit reason and no promotion.

Status: PLANNED.

## Carried invariants

All C002 constraints remain binding. C003 may add runtime adapters and evidence, but it may not weaken promotion, privacy, licensing, security, provider-routing, budget, cache, or rollback controls.
