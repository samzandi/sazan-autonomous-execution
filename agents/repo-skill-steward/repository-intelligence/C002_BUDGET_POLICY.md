# C002 Token and Output Budget Enforcement

Context: C002
Date: 2026-09-30
Status: VERIFIED

Verified lab run: 36757285076

Verified:
- eighteen budget/orchestration contract tests passed;
- strict stage-specific measurements were enforced;
- missing required metrics failed closed;
- cumulative token and output accounting was deterministic;
- graph-node accounting used a maximum ceiling;
- timeout overruns blocked;
- provider truncation blocked by default;
- budget rejection did not mutate the source artifact;
- upstream provider failure remained the primary failure cause;
- legacy non-strict manifests remained compatible.

Verified lab run: 36757285076

Verified:
- 18 budget and orchestration contract tests passed;
- cumulative context-token and output-byte budgets were enforced;
- graph-node usage used the maximum observed graph rather than repeated summation;
- stage timeout overrun blocked execution;
- strict mode blocked missing required measurements;
- context-token measurements required an explicit counting method;
- provider truncation was blocked by default and only allowed as an explicit constrained result;
- exact output-byte and graph-node helpers were validated;
- provider failures remained provider failures rather than being masked by budget enforcement;
- legacy manifests remained non-strict for backward compatibility;
- the final envelope persisted cumulative usage and auditable per-stage budget receipts.

## Purpose

Turn declared run budgets into machine-enforced limits rather than advisory metadata.

## Primary implementation

`scripts/budget_guard.py`

The C002 orchestrator evaluates a budget receipt before committing each stage result to the common evidence envelope.

## Budget dimensions

Run-level limits:
- `max_context_tokens`;
- `max_graph_nodes`;
- `max_output_bytes`;
- `stage_timeout_seconds`.

Stage-local metrics:
- `context_tokens`;
- `context_token_method`;
- `graph_nodes`;
- `output_bytes`;
- `elapsed_seconds`;
- `truncated`.

## Production strict mode

Production manifests enable:

```json
{
  "budget_policy": {
    "strict": true,
    "allow_truncation": false
  }
}
```

Strict mode is fail-closed.

Each stage has a defined set of required measurements:
- L0 intake: output bytes + elapsed time;
- L1 context packaging: context tokens + output bytes + elapsed time;
- L2 semantic graph: graph nodes + output bytes + elapsed time;
- L3 architecture presentation: output bytes + elapsed time;
- L4 Wiki/Q&A: context tokens + output bytes + elapsed time;
- L5 semantic editing: output bytes + elapsed time;
- L6 reverse engineering: context tokens + output bytes + elapsed time;
- L7 promotion: internal policy step; no provider-style measurement is required.

If a required measurement is missing, the stage is blocked.

## Token accounting

When `context_tokens` is reported, its counting method is mandatory.

Accepted methods:
- `provider-reported`;
- `exact-tokenizer`;
- `utf8-byte-upper-bound`.

The last method is explicitly conservative. The guard never silently invents a token estimate.

Context token usage is cumulative across measured stages.

## Output accounting

`output_bytes` is cumulative across measured stages.

The guard includes an exact filesystem byte-count helper. Budget enforcement never rewrites, clips, or truncates the source artifact.

## Graph accounting

`graph_nodes` records the maximum graph size observed in the run instead of summing repeated views of the same graph.

This prevents graph consumers from double-counting the same indexed structure.

## Time accounting

`elapsed_seconds` is checked against `stage_timeout_seconds` for each stage.

The guard validates a measured overrun and blocks it. Actual process cancellation remains the responsibility of the provider runner; that execution-control work belongs to the provider health/fallback milestone.

## Truncation

Provider-reported `truncated: true` blocks by default.

An explicit `allow_truncation: true` policy can convert it to an allowed result with constraints, but this is not the production default.

There is no silent truncation path.

## Decisions

- `allow`;
- `allow-with-constraints`;
- `block`.

A blocked budget receipt converts the stage result to `blocked` and stops orchestration.

## Persisted evidence

Each completed stage stores its budget receipt.

The evidence envelope also stores cumulative `budget_usage`:
- context tokens;
- maximum graph nodes;
- output bytes;
- measured-stage count;
- last measured stage duration.

## Legacy compatibility

When `budget_policy.strict` is absent, the default is false.

This preserves historical L0–L7 fixtures while provider adapters are upgraded. New production workflows must opt into strict mode.

## Invalid telemetry

The guard rejects:
- negative measurements;
- booleans used as numbers;
- fractional integer metrics;
- unsupported token-count methods;
- non-boolean truncation flags.

## Promotion boundary

Budget compliance does not change promotion authority.

A budget-compliant run can only become eligible for parent review; it cannot auto-promote.
