# Semantic Editing Policy

Context: C001
Date: 2026-09-30
Status: VERIFIED

Verified lab run: 36745934710

Verified:
- CodeGraph pre-edit impact evidence found the dependent path;
- Serena 1.7.0 was installed from immutable commit 949a27ef1e5fda1a6e7b561e777bcece345c6ffd;
- uv 0.12.21 was digest-verified for the LSP runtime prerequisite;
- Serena health-check passed with Pyright;
- find_referencing_symbols found the cross-file usage;
- normalize_amount was renamed to normalize_money across files;
- an unreferenced symbol was removed through safe-delete;
- Python compilation and functional execution passed after mutation;
- CodeGraph post-edit verification found the renamed symbol and dependent path.

Operational finding:
- Serena 1.7.0 headless in-process teardown can terminate the calling process while stopping managed language-server processes.
- Production Sazan integration must therefore run Serena behind an isolated MCP/subprocess boundary rather than embedding its application runtime in the primary Sazan process.

## Goal

Provide symbol-aware repository edits with explicit pre-change impact evidence, reference-aware refactoring, and post-change verification.

## Serena license split

Canonical repository: oraios/serena

### Serena 1.7.0

- tag: v1.7.0
- immutable commit: 949a27ef1e5fda1a6e7b561e777bcece345c6ffd
- license: MIT
- project metadata version: 1.7.0

The upstream project identifies v1.7.0 and commit 74c38a65f03fc0764d7ee4b3016ef6a07572ed64 as the final MIT-era cutoff. The v1.7.0 tag resolves to commit 949a27ef1e5fda1a6e7b561e777bcece345c6ffd and its LICENSE and package metadata declare MIT.

Capabilities present in the MIT release include:
- find symbol;
- symbol overview;
- find referencing symbols;
- find declaration / implementations;
- diagnostics;
- symbol rename across the codebase when supported by the language server;
- replace symbol body;
- insert before / after symbol;
- safe delete;
- MCP server operation.

### Serena v2 / current main

The Serena application on current main is GPL-3.0-or-later.

Policy:
- do not vendor or copy current Serena application code into Sazan commercial core;
- do not silently upgrade the pinned MIT adapter to a v2 application build;
- v2 may be evaluated as a separately operated external tool/service through a stable protocol boundary;
- any future redistribution or derivative integration involving v2 requires a deliberate license review.

### SolidLSP

Current Serena separates SolidLSP under MIT in src/solidlsp.

Strategic option:
- treat SolidLSP as a permissive lower-level building block for a future Sazan-owned semantic editing engine;
- do not assume Serena application behavior is included in SolidLSP;
- independently implement Sazan-specific orchestration, policy, and edit contracts if this path is promoted.

## Guarded edit transaction

Every semantic edit should use this sequence when practical:

1. Resolve repository revision and working tree state.
2. Query CodeGraph impact / references before the edit.
3. Refuse or escalate ambiguous high-blast-radius changes.
4. Run the semantic editing provider against a writable isolated branch/worktree.
5. Apply symbol-aware edit/refactor.
6. Run language diagnostics and repository tests/build checks.
7. Re-index CodeGraph.
8. Verify the renamed/changed symbol and dependent paths after the edit.
9. Persist an evidence record containing provider/version, files changed, pre/post impact, tests, and rollback commit.

## Baseline provider routing

- primary provider: Serena 1.7.0, pinned by immutable commit and operated behind an MCP/subprocess boundary;
- structural safety gate: CodeGraph 0.20.1;
- future permissive implementation candidate: SolidLSP + Sazan-owned editing adapter;
- Serena v2: external/reference-only unless a separate licensing decision is made.

## Safety rules

- never edit directly on the protected default branch;
- require a branch/worktree and rollback point;
- semantic rename is preferred over regex replacement for identifiers;
- safe-delete must prove there are no references or stop;
- destructive edit tools require explicit execution authorization from the parent workflow;
- run post-edit verification even when the semantic provider reports success;
- private repository code must stay within the approved execution boundary.
