# C002 Diff → Impact Normalization

Context: C002
Date: 2026-09-30
Status: REVALIDATION / LAB VALIDATION

Previous verified lab: 36755232124

## Hardening objective

Replace synthetic global impact scoring with an evidence-first separation of:
- local semantic risk reported by the local provider;
- observed/inferred evidence confidence;
- factual cross-repository blast radius.

The previous implementation remains historical evidence only until this revalidation passes.

## Purpose

Translate repository changes into an evidence-backed cross-repository blast radius without guessing impact from filenames, repository counts, or change type alone.

## Inputs

The canonical normalizer consumes:
- verified privacy-safe multi-repository registry;
- matched contract graph;
- verified process/execution-flow report;
- evidence-backed change observations;
- local semantic-impact evidence, preferably from CodeGraph.

## Change contract

Each change records:
- change ID;
- repository ID;
- change type: add / modify / delete / rename / version-change;
- surface kind;
- identifier;
- observed/inferred claim state;
- evidence and rationale when inferred;
- optional local semantic impact;
- optional explicit contract touches.

Baseline surfaces:
- file;
- symbol;
- contract;
- http-api;
- event;
- schema;
- package;
- cli;
- storage;
- custom.

## Local semantic impact

For file/symbol changes, local evidence may carry:
- provider-reported risk level;
- impacted symbols;
- affected files;
- related tests;
- direct callers;
- impacted process-step IDs;
- evidence references.

Sazan preserves the provider's local risk. It does not recompute a synthetic global risk score.

A file/symbol change without adequate semantic mapping becomes `partial-evidence`.

## Contract touches

A local code change only crosses a repository boundary when evidence explicitly maps it to a matched contract.

Each contract touch records:
- contract ID;
- side: provider / consumer / both;
- observed or inferred state;
- evidence;
- rationale when inferred.

The changed repository must be a party to the contract and the declared side must match ownership.

Contract-surface changes may use a top-level contract ID as shorthand.

## Propagation

The normalizer:
1. maps local symbols/steps;
2. maps explicit contract touches;
3. identifies process-flow edges bound to those contracts;
4. finds the earliest affected point in each complete flow;
5. propagates review scope downstream;
6. aggregates affected repositories, contracts, flows, steps, tests, and files.

Upstream repositories are not marked solely because they precede a local change.
A contract touch may include the counterparty because the cross-repository surface itself requires validation.

## Version compatibility

For provider-side version changes:
- compare the new supplied version with the recorded consumer requirement.

For consumer-side version changes:
- compare the new required version with the recorded provider version.

A mismatch is a compatibility finding, not a claim that runtime failure has already occurred.

## Confidence

Evidence confidence is separate from local risk:
- observed — every material mapping is directly evidenced;
- inferred — at least one material change/contract mapping is inferred.

Inferred mappings propagate explicit constraints.

## Privacy

The normalizer operates on opaque repository IDs.

For private/internal repositories:
- source names are not required;
- absolute provider paths are converted to repository-relative paths when a runtime root is supplied;
- otherwise absolute paths are replaced by an opaque hash plus basename.

## Outputs

`scripts/diff_impact_normalizer.py` produces:
- normalized JSON blast radius;
- Markdown review summary;
- preserved local risk and related tests;
- evidence confidence;
- compatibility findings;
- test/review scope;
- incomplete-evidence findings.

## Non-goal

The layer does not produce a synthetic global low/medium/high/critical score from topology size or change type.
