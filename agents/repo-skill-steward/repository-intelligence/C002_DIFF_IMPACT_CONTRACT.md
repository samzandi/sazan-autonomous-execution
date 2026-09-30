# C002 Diff → Impact Normalization

Context: C002
Date: 2026-09-30
Status: LAB VALIDATION

## Purpose

Normalize repository-local diffs into one evidence-backed cross-repository blast-radius report.

## Local evidence source

Primary local diff evidence:
- CodeGraph Community 0.20.1 `codegraph_pr_context`;
- CodeGraph `analyze_impact` when a single symbol requires focused pre-change analysis.

The pinned 0.20.1 release already includes `codegraph_pr_context`, which:
- runs `git diff` against a base branch;
- identifies changed files/functions;
- classifies changed functions;
- reports callers;
- reports related tests and test gaps;
- reports affected modules;
- emits a local risk level.

Sazan does not treat CodeGraph's repository-local risk as the final system blast radius.

## Sazan normalization layer

`scripts/diff_impact_normalizer.py` combines:
- local diff impact;
- multi-repository registry;
- matched contract graph;
- verified process-flow graph;
- evidence-backed mappings from changed artifacts to flow steps and contract sides.

## Change observations

Each normalized change records:
- repository ID;
- change ID;
- change type;
- file/symbol when available;
- observed or inferred state;
- local risk;
- locally affected symbols/files/tests;
- touched process steps;
- touched contracts and the changed side.

Supported baseline change types:
- body
- signature
- rename
- delete
- schema
- contract
- event
- file
- config

## Contract propagation

Provider-side contract changes propagate to consumers.

Consumer-side contract changes trigger provider counterparty review.

Shared contract changes propagate to the other contract participant.

Breaking surface changes such as signature/delete/schema/contract/event changes are escalated to high contract risk.

## Flow propagation

A change affects a process flow when it touches:
- a step present in that flow; or
- a contract used by that flow.

The report identifies downstream repositories from the earliest changed point in that flow.

Any inferred change, contract hop, or flow evidence propagates an inferred constraint.

## Risk

Risk and confidence are separate concepts.

Risk:
- local CodeGraph risk is the baseline;
- signature/delete changes are at least high;
- schema/contract/event changes are at least medium locally and high when they affect a matched contract;
- cross-repository process impact is at least medium.

Confidence/state:
- OBSERVED when the supporting mappings and flow evidence are observed;
- INFERRED when any required mapping is inferred.

## Outputs

- normalized changes;
- affected repositories with reasons;
- affected contracts;
- affected flows and downstream repositories;
- related test targets;
- risk level;
- constraints;
- blockers;
- Markdown summary.

## Privacy

The normalizer consumes privacy-safe repository IDs.
Private repository source names are not required and must not be added to impact outputs.
