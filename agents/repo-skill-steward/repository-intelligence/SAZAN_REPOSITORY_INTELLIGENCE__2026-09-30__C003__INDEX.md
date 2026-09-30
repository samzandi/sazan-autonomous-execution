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

Status: BLOCKED — live Codex runtime reached model execution, but OpenAI API quota is exhausted; promotion forbidden until a verified live run completes.

## Carried invariants

All C002 constraints remain binding. C003 may add runtime adapters and evidence, but it may not weaken promotion, privacy, licensing, security, provider-routing, budget, cache, or rollback controls.


### Milestone 1 implementation

- `C003_CODEX_RUNTIME_PROOF.md`;
- `prompts/c003_codex_runtime_proof.md`;
- `schemas/c003_codex_runtime_proof.schema.json`;
- `scripts/validate_c003_codex_runtime_proof.py`;
- `tests/test_repository_intelligence_c003_codex_runtime_proof.py`;
- `.github/workflows/repository-intelligence-c003-codex-runtime-proof.yml`.

Runtime contract:
- official Codex GitHub Action pinned by commit SHA;
- Codex CLI pinned to 0.159.2;
- gpt-5.6-sol pinned as the runtime model;
- read-only permission profile and drop-sudo safety strategy;
- prompt-file usage instead of an inline prompt;
- schema-constrained Codex output;
- deterministic C002 baseline before the live run;
- independent non-model validation after the live run;
- fail closed when OPENAI_API_KEY is absent or any invariant fails.


### Milestone 1 live evidence

- workflow run: 36766115291;
- OPENAI_API_KEY presence check: PASSED after configuration;
- proof tooling validation: PASSED;
- deterministic C002 baseline: PASSED;
- Codex 0.159.2 startup: PASSED;
- model: gpt-5.6-sol;
- sandbox: read-only;
- approval mode: never;
- safety strategy: drop-sudo;
- live inference: BLOCKED by OpenAI API quota;
- repeated run reproduced the same external blocker;
- no merge or promotion is permitted while blocked.
