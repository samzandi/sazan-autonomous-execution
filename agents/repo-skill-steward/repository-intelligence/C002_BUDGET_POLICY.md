# C002 Token and Output Budget Enforcement

Context: C002
Date: 2026-09-30
Status: LAB VALIDATION

## Purpose

Turn declared run budgets into machine-enforced limits instead of advisory metadata.

## Guard

Primary implementation:
`scripts/budget_guard.py`

The guard is evaluated for every stage result before the result is committed to the common evidence envelope.

## Recognized stage-local metrics

- `context_tokens`
- `graph_nodes`
- `output_bytes`
- `elapsed_seconds`
- `truncated`

Unknown metrics are preserved in stage evidence but ignored by the budget engine so existing provider-specific telemetry remains compatible.

## Budget semantics

### Context tokens

`max_context_tokens` is cumulative across measured stages.

Each provider reports only the tokens attributable to that stage result. The guard accumulates them in the run envelope.

### Output bytes

`max_output_bytes` is cumulative across measured stages.

It represents persistable output produced by Repository Intelligence, not upstream repository size.

### Graph nodes

`max_graph_nodes` is a run ceiling on the largest graph-node count reported by a stage.

The guard stores the maximum rather than summing the same graph across multiple graph consumers.

### Stage timeout

`stage_timeout_seconds` is checked independently for every stage against `elapsed_seconds`.

The guard does not terminate external processes itself. Provider adapters/runners remain responsible for enforcing wall-clock cancellation; the orchestration gate rejects a reported overrun.

## Decisions

- `allow`
- `allow-with-constraints`
- `block`

A hard budget violation converts the stage result to `blocked` and stops orchestration.

A provider-reported `truncated: true` produces `allow-with-constraints` when no hard limit is exceeded.

## Missing metrics

Legacy or provider-specific stage results may omit recognized metrics.

Missing measurements:
- do not become fabricated zeros in provider evidence;
- do not block by themselves;
- are listed as unmeasured by the guard.

This keeps the existing L0–L7 fixtures compatible while new adapters progressively adopt the common metrics.

## Invalid metrics

Negative, boolean-as-number, non-numeric, fractional integer metrics, and non-boolean `truncated` values are rejected.

## Persisted usage

The evidence envelope stores cumulative `budget_usage`:
- context tokens;
- maximum graph nodes;
- output bytes;
- number of measured stages;
- last measured stage duration.

## Promotion boundary

Budget enforcement does not change promotion authority.
A budget-compliant run can only reach `ready-for-parent-review`; it cannot auto-promote.
