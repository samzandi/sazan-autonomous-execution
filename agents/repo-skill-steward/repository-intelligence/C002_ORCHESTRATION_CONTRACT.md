# C002 Orchestration and Evidence Envelope Contract

Context: C002
Date: 2026-09-30
Status: VERIFIED

Verified lab run: 36750536038

Verified:
- nine orchestration contract tests passed;
- L0→L7 ordering was enforced;
- analysis mode skipped L5 semantic editing;
- a complete run reached ready-for-parent-review through the verified L7 gate;
- constrained verifier output propagated to the final envelope;
- private repository source identity was replaced by an opaque repository ID;
- auto-promotion remained disabled.

## Goal

Provide one deterministic entry point across the verified Repository Intelligence layers while keeping provider execution, evidence, policy, and parent approval separate.

## Entry point

`scripts/orchestrate_repository_intelligence.py`

Inputs:
- run manifest;
- directory of stage-result envelopes.

Outputs:
- deterministic execution plan;
- common evidence envelope;
- L7 promotion decision when all prerequisite stages pass.

## Stage order

1. L0-intake
2. L1-context-packaging
3. L2-semantic-graph
4. L3-architecture-presentation
5. L4-wiki-qa
6. L5-semantic-editing
7. L6-reverse-engineering
8. L7-promotion

L5 is automatically skipped for analysis-only runs.

## Common evidence envelope

Every stage records:
- stage ID;
- terminal status;
- provider;
- evidence references;
- artifact references;
- metrics;
- constraints;
- error state.

Cross-cutting gates carry:
- license;
- security;
- capability delta;
- rollback;
- private-data handling;
- verifier decision.

## Privacy

For public or local-fixture repositories, the canonical source may be retained in the run envelope.

For private/internal repositories:
- source identity is replaced by a deterministic opaque repository ID;
- `identity_persisted=false`;
- the public repository must never contain the private source name.

## Budgets

Each run carries explicit upper bounds for:
- context tokens;
- graph nodes;
- output bytes;
- stage timeout seconds.

Provider adapters must honor these budgets when they are wired into the orchestrator.

## Failure semantics

- failed stage → run failed;
- blocked stage → run blocked;
- missing next-stage result → run remains running;
- constrained pass → constraints propagate;
- promotion can only be evaluated after all required pre-L7 stages pass.

## Promotion

The orchestrator delegates policy to the verified L7 promotion gate.

It cannot auto-promote.
A successful machine decision only moves the run to `ready-for-parent-review`.
