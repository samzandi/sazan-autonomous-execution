# C003 Runtime / Provider Contract Parity

Context: C003
Date: 2026-09-30
Status: ENGINE CANDIDATE
Milestone: 3

## Goal

Compare verified live Repository Intelligence proofs from Codex and Claude Code without treating provider-specific implementation differences as semantic differences.

## Fail-closed rules

A parity verdict can be VERIFIED only when both provider reports are already VERIFIED and both preserve the C002/C003 invariants.

Required provider invariants:
- repository HEAD was independently matched;
- runtime model and CLI version were recorded;
- deterministic C002 baseline passed;
- focused regression tests passed;
- parent-review boundary remained enforced;
- automatic promotion remained disabled;
- private identity redaction remained enforced;
- workspace remained unchanged;
- evidence was present;
- persisted evidence contained no sensitive markers;
- provider report contained no blockers.

Required equalities across providers:
- repository HEAD;
- deterministic baseline SHA-256;
- baseline orchestration state.

Allowed provider differences:
- runtime/provider name;
- model;
- CLI version;
- pinned action commit;
- provider proof fingerprint.

## Implementation

- `scripts/runtime_contract_parity.py`;
- `tests/test_repository_intelligence_c003_runtime_parity.py`;
- `.github/workflows/repository-intelligence-c003-runtime-parity-lab.yml`.

## Live status

The parity engine can be independently verified before live provider credentials are available.

A live parity verdict remains BLOCKED until both Milestone 1 and Milestone 2 produce verified runtime-proof reports on the same repository HEAD and deterministic baseline.
