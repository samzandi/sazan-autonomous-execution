# Sazan Repository Intelligence — C002 Index

Context: C002
Date: 2026-09-30
Status: ACTIVE
Topic: End-to-End Orchestration and Multi-Repository Productionization

## Objective

Turn the verified L0–L7 components into one operational Repository Intelligence pipeline that can analyze repositories reproducibly, route evidence between layers, reason across repository boundaries, and produce promotion-ready outputs.

## Initial scope

- orchestration entry point — IMPLEMENTED, pending lab;
- common evidence-envelope schema — IMPLEMENTED, pending lab;
- multi-repository registry;
- cross-repository contracts;
- process-flow synthesis;
- diff-impact normalization;
- token and output budgets;
- provider fallback/health controls;
- incremental state/cache strategy;
- realistic end-to-end integration lab.

## Milestone 1 — Single-repository orchestration

Implementation:
- `scripts/evidence_envelope.py`;
- `scripts/orchestrate_repository_intelligence.py`;
- `C002_ORCHESTRATION_CONTRACT.md`.

The orchestrator:
- enforces L0→L7 ordering;
- skips L5 automatically for analysis-only runs;
- applies run-level token/graph/output/timeout budgets;
- redacts private/internal repository identity from persisted output;
- propagates stage constraints and cross-cutting gates;
- delegates the final decision to the verified L7 promotion engine;
- can only reach `ready-for-parent-review`, never auto-promotion.

Status: pending C002 orchestration lab.

## Constraints carried from C001

- parent steward remains final promotion authority;
- no auto-promotion;
- no private repository identities in this public repository;
- license/integration-mode policy remains mandatory;
- commercial core must remain independent from non-commercial/reference-only implementations;
- semantic edits stay branch/worktree isolated;
- every new executable path requires lab evidence and rollback.
