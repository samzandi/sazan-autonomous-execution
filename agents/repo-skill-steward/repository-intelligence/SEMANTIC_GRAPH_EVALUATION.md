# Semantic Graph Evaluation — CodeGraph vs GitNexus

Context: C001
Date: 2026-09-30
Status: VERIFIED

## Decision

CodeGraph Community is promoted as the primary semantic graph engine for Sazan Repository Intelligence.

Canonical repository: codegraph-ai/CodeGraph
Pinned version: 0.20.1
License: Apache-2.0
Primary operating mode: graph-only for deterministic structural analysis and CI
Telemetry policy: off
Verified lab run: 36740772666
Linux x86_64 SHA-256: 32b26422fa5ffe0a130955b7f7df771f722b2d427d67f53f104d9907bdfb24a6

## Verified lab evidence

The isolated lab created a three-layer Python fixture:
- core.money.normalize_amount
- service.orders.calculate_total
- api.checkout.handle_checkout

The pinned CodeGraph binary successfully verified:
- symbol search for normalize_amount;
- cross-file caller discovery from normalize_amount to calculate_total;
- dependency graph traversal from service/orders.py toward core/money.py;
- impact analysis showing calculate_total in the blast radius of normalize_amount.

The workflow used:
- repository permission: contents read;
- no user secrets;
- CODEGRAPH_TELEMETRY=off;
- graph-only mode;
- a release binary whose SHA-256 matched the canonical GitHub release metadata.

## Community capabilities used by Sazan

- multi-language semantic indexing;
- symbol search;
- callers and callees;
- call graph;
- dependency graph;
- impact analysis;
- entry-point discovery;
- related-test discovery;
- module summaries;
- circular dependency detection;
- architecture document generation;
- documentation verification;
- MCP exposure;
- narrowed tool profiles;
- persistent project-scoped memory/docs surfaces when enabled.

## GitNexus benchmark boundary

Canonical repository: nxpatterns/gitnexus
License: PolyForm Noncommercial 1.0.0
Status: reference-only; no commercial embedding.

GitNexus remains an architectural benchmark for capabilities Sazan may independently implement:
- process/execution-flow discovery;
- community clustering;
- precomputed relational context;
- multi-repository registry;
- repository groups and cross-repository contract registry;
- diff-to-impact detection;
- response token budgets;
- graph-enriched agent hooks;
- optional PDG, control/data dependence, and taint analysis;
- graph-backed plan/work/review workflows.

These are requirements and design references only. Do not copy or vendor GitNexus implementation into Sazan commercial components.

## Sazan-owned abstraction

CodeGraph is an engine, not the Sazan architecture.

Sazan retains ownership of:
- canonical repository identity and cross-repo registry;
- evidence schema;
- graph-provider adapter contract;
- process/flow synthesis;
- normalized change-impact reports;
- token-budgeted graph evidence envelopes;
- policy and promotion gates;
- future PDG/taint adapters;
- fallback graph providers.

This separation allows CodeGraph to be upgraded or replaced without changing the higher-level Repository Intelligence contract.
