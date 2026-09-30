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

Status: BLOCKED — implementation exists in PR #29; live Codex 0.159.2 reached gpt-5.6-sol execution but OpenAI API quota is exhausted. Promotion is forbidden until a verified rerun completes.

## Carried invariants

All C002 constraints remain binding. C003 may add runtime adapters and evidence, but it may not weaken promotion, privacy, licensing, security, provider-routing, budget, cache, or rollback controls.


## Milestone 2 — Claude Code runtime proof

Goal:
- execute the promoted Repository Intelligence flow through an authorized Claude Code runtime;
- preserve the same parent-review, privacy, workspace-integrity, and deterministic-baseline guarantees used by the Codex proof;
- capture runtime model/version, evidence, and independent validation;
- support either ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN without persisting either secret.

Current evidence:
- implementation: PR #30;
- workflow run: 36767883113;
- checkout: PASSED;
- authentication preflight: BLOCKED because neither supported Claude credential is configured;
- live Claude execution: NOT STARTED;
- merge/promotion: forbidden while blocked.

Status: BLOCKED — external Claude authentication is required.

## Milestone 3 — Runtime / provider contract parity

Implementation:
- `scripts/runtime_contract_parity.py`;
- `tests/test_repository_intelligence_c003_runtime_parity.py`;
- `C003_RUNTIME_CONTRACT_PARITY.md`;
- `.github/workflows/repository-intelligence-c003-runtime-parity-lab.yml`.

Model:
- both provider reports must already be VERIFIED;
- both must target the same repository HEAD;
- both must use the same deterministic C002 baseline SHA-256;
- both must preserve `ready-for-parent-review`;
- privacy, workspace integrity, evidence presence, and sensitive-marker checks must pass;
- provider-specific model, CLI version, action commit, and proof fingerprint may differ;
- any blocker or invariant mismatch fails closed.

Engine status: VERIFIED / PROMOTED — workflow run 36768157558; all repository regressions passed; PR #31 merged as commit 9f25127b019ae42c58d5beda56f7860dcb24f1f8.

Live parity verdict: BLOCKED until Milestone 1 and Milestone 2 both produce verified proofs on the same revision and deterministic baseline.


## Milestone 4 — Failure and rollback evidence

Implementation:
- `scripts/rollback_evidence.py`;
- `scripts/run_c003_failure_rollback_lab.py`;
- `tests/test_repository_intelligence_c003_rollback.py`;
- `C003_FAILURE_ROLLBACK_EVIDENCE.md`;
- `.github/workflows/repository-intelligence-c003-failure-rollback-lab.yml`;
- promotion gate hardening in `scripts/evaluate_promotion.py`.

Model:
- failure must be observed rather than inferred;
- execution must occur in an isolated git worktree;
- rollback revision and tree hash must be recorded before mutation;
- the mutation revision must differ from the rollback point;
- rollback must restore both revision and tree exactly;
- candidate worktree must be clean after rollback;
- parent workspace must remain unchanged;
- functional validation must pass after rollback;
- private/sensitive material and absolute execution paths must not be persisted;
- promotion rollback status now requires evidence, not status alone.

Status: VERIFIED / PROMOTED — real rollback lab run 36769117578 passed; promotion gate now requires rollback evidence; all repository regressions passed.


## Milestone 5 — Reproducibility pack

Implementation:
- `reproducibility/c003_reproducibility_spec.json`;
- `scripts/build_reproducibility_pack.py`;
- `scripts/validate_reproducibility_pack.py`;
- `tests/test_repository_intelligence_c003_reproducibility.py`;
- `C003_REPRODUCIBILITY_PACK.md`;
- `.github/workflows/repository-intelligence-c003-reproducibility-pack-lab.yml`.

Model:
- exact Git revision and tree hash are recorded;
- workspace must be clean;
- required implementation/workflow files are SHA-256 fingerprinted;
- external tools are version/commit pinned and record artifact hashes where the verified workflows enforce them;
- verified workflow run IDs are retained;
- live Codex/Claude blockers remain explicit rather than being promoted to success;
- reproduction commands are retained;
- pack generation is deterministic and contains no timestamp or machine-specific absolute path;
- a canonical pack fingerprint detects evidence drift.

Status: VERIFIED / PROMOTED — deterministic reproducibility run 36770061102 passed; byte-identical pack generation, manifest validation, core reproduction commands, and all repository regressions passed.
