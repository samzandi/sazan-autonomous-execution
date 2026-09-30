# Sazan Repository Intelligence — C002 Index

Context: C002
Date: 2026-09-30
Status: ACTIVE
Topic: End-to-End Orchestration and Multi-Repository Productionization

## Objective

Turn the verified L0–L7 components into one operational Repository Intelligence pipeline that can analyze repositories reproducibly, route evidence between layers, reason across repository boundaries, and produce promotion-ready outputs.

## Initial scope

- orchestration entry point — VERIFIED / PROMOTED;
- common evidence-envelope schema — VERIFIED / PROMOTED;
- multi-repository registry — VERIFIED / PROMOTED;
- cross-repository contracts — VERIFIED / PROMOTED;
- process-flow synthesis — VERIFIED / PROMOTED;
- diff-impact normalization — IMPLEMENTED, pending lab;
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

Status: VERIFIED — orchestration lab run 36750536038; 9 contract tests passed.

## Constraints carried from C001

- parent steward remains final promotion authority;
- no auto-promotion;
- no private repository identities in this public repository;
- license/integration-mode policy remains mandatory;
- commercial core must remain independent from non-commercial/reference-only implementations;
- semantic edits stay branch/worktree isolated;
- every new executable path requires lab evidence and rollback.


## Milestone 2 — Multi-repository registry and contracts

Implementation:
- `scripts/multi_repo_registry.py`;
- `C002_MULTI_REPO_CONTRACT.md`;
- multi-repository contract unit tests;
- four-repository integration lab.

Model:
- repositories declare evidence-backed `provides` and `requires` observations;
- matching produces directed provider→consumer contracts;
- upstream/downstream topology is generated automatically;
- internal unresolved, ambiguous, or version-incompatible contracts block the workspace;
- external requirements are recorded without pretending they are internally provided;
- private/internal repositories require stable opaque IDs and never persist source names.

Status: VERIFIED — multi-repository lab run 36751884638; 13 unit/integration checks passed.


## Milestone 3 — Process / execution flow synthesis

Implementation:
- `scripts/process_flow_synthesis.py`;
- `C002_PROCESS_FLOW_CONTRACT.md`;
- process-flow unit tests;
- multi-repository execution-flow integration lab.

Model:
- local process steps and edges remain evidence-backed inside each repository;
- crossing a repository boundary requires an already matched cross-repository contract;
- runtime direction is explicit rather than inferred from provider/consumer ownership;
- complete entry→terminal paths aggregate step, edge, and contract evidence;
- any inferred hop downgrades the complete path to inferred;
- cycles and unreachable steps are reported;
- max-hops and max-paths prevent runaway traversal.

Status: VERIFIED — process-flow lab run 36753107333; 11 contract tests plus end-to-end multi-repository flow validation passed.


## Milestone 4 — Diff → Impact normalization

Implementation:
- `scripts/diff_impact_normalize.py`;
- `C002_DIFF_IMPACT_CONTRACT.md`;
- diff-impact contract tests;
- CodeGraph-backed multi-repository integration lab.

Model:
- file/symbol changes require local semantic-impact evidence rather than filename guesses;
- changed symbols map explicitly to process steps;
- API/event/schema/package changes bind to matched contract IDs;
- contract changes mark both parties and propagate through verified process flows;
- version changes are compared with recorded consumer requirements;
- unmapped changes remain `partial-evidence`;
- review scope contains repositories, contracts, and flows rather than a speculative numeric risk score;
- inferred change observations retain explicit constraints;
- private repository identities remain opaque.

Status: pending C002 diff-impact lab.
