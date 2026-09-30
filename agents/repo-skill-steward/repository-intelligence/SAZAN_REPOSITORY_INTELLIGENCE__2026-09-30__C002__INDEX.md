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
- diff-impact normalization — VERIFIED / PROMOTED;
- token and output budgets — VERIFIED / PROMOTED;
- provider fallback/health controls — VERIFIED / PROMOTED;
- incremental state/cache strategy — VERIFIED / PROMOTED;
- realistic end-to-end integration lab — VERIFIED / PROMOTED;

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
- diff-impact unit tests;
- CodeGraph-backed cross-repository integration lab.

Model:
- local semantic impact is collected from CodeGraph or another normalized provider;
- local file/symbol/test impact is preserved;
- explicit changed contract IDs propagate review to provider/consumer repositories;
- changed process steps and contract edges propagate into downstream end-to-end flows;
- affected tests, contracts, flows, steps, files, and repositories form a unified blast radius;
- private absolute paths are converted to relative or opaque persistable paths;
- contract version mismatches become explicit compatibility findings;
- missing semantic mapping remains partial-evidence rather than guessed impact.

Status: VERIFIED — diff-impact lab run 36755232124; 11 contract tests plus real CodeGraph cross-repository propagation validation passed.


## Milestone 5 — Token, graph, output, and stage-time budgets

Implementation:
- `scripts/budget_guard.py`;
- `C002_BUDGET_POLICY.md`;
- budget contract tests;
- strict orchestration integration lab.

Model:
- stage-specific required usage is machine-checked in strict mode;
- context tokens and output bytes accumulate across stages;
- graph nodes use a maximum ceiling rather than repeated summation;
- stage elapsed time is checked independently;
- context-token reports must identify their counting method;
- provider truncation blocks by default;
- a budget rejection never mutates the source artifact;
- every stage persists a budget receipt and the envelope persists cumulative usage;
- legacy manifests remain non-strict until explicitly upgraded.

Status: VERIFIED — budget lab run 36757285076; 18 contract tests plus strict orchestration validation passed.


## Milestone 6 — Provider health and fallback controls

Implementation:
- scripts/provider_health.py;
- C002_PROVIDER_HEALTH_CONTRACT.md;
- provider-routing unit tests;
- orchestration integration tests;
- provider health/fallback lab.

Model:
- provider health and stage eligibility are evaluated separately;
- every strict health observation requires evidence;
- fallback candidates must satisfy the same stage capability contract;
- the only baseline automatic fallback is Repomix to Gitingest for L1 context packaging;
- Code2Prompt remains a scoped agent/MCP path rather than a silent full-context substitute;
- degraded providers require explicit opt-in;
- private/internal targets require private-safe candidates;
- orchestration enforces that stage output comes from the routed provider;
- fallback selection is persisted as a receipt and constraint;
- stages without an equivalent promoted fallback fail closed.

Status: VERIFIED — provider health lab run 36759816437; 27 provider-routing/orchestration tests plus explicit fallback and fail-closed validation passed.


## Milestone 7 — Incremental state and cache strategy

Implementation:
- `scripts/incremental_cache.py`;
- `C002_INCREMENTAL_CACHE_CONTRACT.md`;
- incremental-cache unit tests;
- cross-revision invalidation lab.

Model:
- cache identity is based on semantic stage inputs rather than branch names or timestamps;
- source revision is preserved as provenance but is not automatically a cache invalidator;
- cross-revision reuse is allowed only when stage input, provider/version/contract, policy, implementation, and dependency fingerprints are unchanged;
- same-revision-only mode is available for volatile or mutating stages;
- upstream dependency changes invalidate downstream cache entries;
- cache-key integrity and result fingerprints are mandatory;
- private repository source names are not required by cache metadata;
- cache hits never bypass provider health, budgets, license/security, verifier, or parent promotion gates.

Status: VERIFIED — incremental-cache lab run 36763808082; 19 contract tests plus cross-revision hit/invalidation validation passed.


## Milestone 8 — Realistic end-to-end integration lab

Implementation:
- `scripts/run_c002_e2e_lab.py`;
- `C002_END_TO_END_LAB.md`;
- end-to-end integration tests;
- pull-request integration workflow.

Scenario:
- four repositories participate in one checkout workspace;
- three internal contracts are matched across repository boundaries;
- one observed entry-to-terminal flow crosses web, API, and a private worker;
- an API event change propagates downstream review impact;
- Repomix is deliberately unhealthy so the promoted Gitingest fallback is exercised;
- strict budget telemetry is enforced across the L0→L7 orchestration path;
- an L2 cache result is reused across revisions only under unchanged semantic fingerprints;
- private repository source identity must not appear in persisted outputs;
- the final machine state must remain `ready-for-parent-review` with auto-promotion disabled.

Status: VERIFIED — end-to-end lab run 36764817135; dedicated end-to-end tests, full C002 regression suite, executable lab assertions, provider fallback, strict budgets, cross-revision cache reuse, parent-review gate, and privacy-redaction checks passed.
