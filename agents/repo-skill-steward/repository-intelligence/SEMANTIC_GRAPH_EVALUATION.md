# Semantic Graph Evaluation — CodeGraph vs GitNexus

Context: C001
Date: 2026-09-30
Status: LAB VALIDATION

## Decision frame

The Sazan Repository Intelligence layer needs a commercially compatible semantic graph engine that can expose symbol, call, dependency, and impact evidence to agents.

## CodeGraph

Canonical repository: codegraph-ai/CodeGraph
Pinned evaluation version: 0.20.1
License: Apache-2.0

Community capabilities relevant to Sazan:
- 38-language tree-sitter parsing;
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
- MCP server;
- graph-only mode for CI and low-resource structural analysis;
- persistent project-scoped memory and docs surfaces;
- narrowed MCP profiles to reduce tool-context overhead.

Security and deployment notes:
- community binary can run in graph-only mode with no embedding model;
- official release publishes SHA-256 digests;
- telemetry can be disabled with CODEGRAPH_TELEMETRY=off;
- built-in exclusions cover common build/cache, credential directories, and secret file extensions;
- the community repository is Apache-2.0, suitable for commercial integration subject to normal license/NOTICE obligations.

## GitNexus benchmark

Canonical repository: nxpatterns/gitnexus
License: PolyForm Noncommercial 1.0.0
Integration status: reference-only for Sazan commercial work.

Architectural capabilities worth reproducing independently where valuable:
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

These are benchmark requirements, not permission to copy GitNexus code or embed its implementation.

## Core strategy

Use CodeGraph community as the first Sazan semantic graph engine if the isolated lab verifies:
1. symbol discovery;
2. cross-file caller discovery;
3. import/dependency relationships;
4. impact analysis;
5. digest-pinned binary execution;
6. read-only, no-secret CI operation.

Keep Sazan orchestration, evidence contracts, policy gates, multi-repo registry, and future higher-order graph intelligence independent from any single upstream engine.

## Planned gap layer

Features not delegated permanently to CodeGraph should live in Sazan-owned adapters and graph services:
- cross-repository registry and identity;
- process/flow synthesis across repositories;
- change-impact normalization;
- token-budgeted graph evidence envelopes;
- optional PDG/taint adapters;
- engine-independent graph schema;
- fallback graph providers.

No new top-level repository is required for this stage. The existing Repository Intelligence module owns the abstraction.
