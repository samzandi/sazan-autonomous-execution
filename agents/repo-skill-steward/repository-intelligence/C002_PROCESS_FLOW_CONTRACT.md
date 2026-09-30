# C002 Process and Execution Flow Synthesis

Context: C002
Date: 2026-09-30
Status: LAB VALIDATION

## Purpose

Reconstruct evidence-backed end-to-end execution paths that cross repository boundaries.

## Inputs

The synthesizer consumes:
- verified multi-repository registry;
- verified matched contract graph;
- per-repository process observations;
- explicit bindings from matched contracts to provider/consumer steps.

## Step observations

Each step records:
- step ID;
- repository ID;
- human label;
- optional symbol;
- operation kind;
- entry / terminal flags;
- observed or inferred state;
- evidence;
- rationale when inferred.

## Intra-repository edges

Local edges describe symbol/process movement inside one repository.
They must not cross repository boundaries.

Examples:
- UI handler → HTTP client
- HTTP route → service function
- service function → event publisher
- event consumer → storage writer

## Cross-repository bindings

Repository boundaries are crossed only through an already matched contract.

A binding must identify:
- contract ID;
- provider-side step;
- consumer-side step;
- runtime flow direction;
- evidence;
- observed/inferred state.

Direction is explicit because contract ownership and runtime execution direction are not always the same:
- HTTP request usually flows consumer → provider;
- event delivery usually flows provider → consumer.

The synthesizer never guesses this direction.

## Output

Outputs:
- normalized step graph;
- local and cross-repository edges;
- all bounded entry→terminal flows;
- repository sequence per flow;
- flow-level observed/inferred state;
- aggregated evidence and constraints;
- cycle report;
- unreachable steps;
- blockers and truncation state;
- Markdown human-readable flow summary.

## Claim semantics

A complete flow is OBSERVED only when every step and edge in that flow is observed.
Any inferred step, edge, or contract downgrades the complete flow to INFERRED and propagates a constraint.

## Budgets

Baseline limits:
- max_hops;
- max_paths.

Path enumeration is simple-path bounded to avoid runaway traversal.

## Blocking

The baseline blocks when no complete entry→terminal flow can be established.
Cycles are reported but are not automatically blockers because retry loops and event cycles can be legitimate.

## Privacy

The flow layer consumes repository IDs from the privacy-safe registry.
It does not need private repository source names.
