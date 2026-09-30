# C002 Diff to Impact Normalization

Context: C002
Date: 2026-09-30
Status: VERIFIED

Verified lab run: 36755232124

Verified:
- eleven diff-impact contract tests passed;
- CodeGraph 0.20.1 performed real local impact analysis on the changed API symbol;
- local semantic evidence was normalized into a cross-repository blast radius;
- the downstream private worker and impacted end-to-end flow were selected for review;
- affected local test scope was retained;
- private absolute/source paths did not leak into persisted impact output;
- a deliberate event contract version mismatch produced a CRITICAL compatibility finding;
- local-only helper changes did not expand cross-repository scope without evidence;
- incomplete semantic mapping remained partial-evidence instead of guessed impact;
- deterministic output was verified.

## Purpose

Convert repository-level changes into a normalized, evidence-backed blast radius across:
- local files and symbols;
- affected tests;
- cross-repository contracts;
- end-to-end process flows;
- downstream repositories.

## Inputs

The normalizer consumes:
- verified multi-repository registry;
- verified matched contract graph;
- verified process-flow report;
- one or more evidence-backed change observations.

Each change records:
- change ID;
- repository ID;
- change type;
- surface kind;
- identifier;
- observed/inferred claim state;
- evidence;
- optional contract IDs;
- local semantic-impact evidence.

## Local semantic impact

The baseline provider is CodeGraph Community 0.20.1.

The normalizer accepts the stable impact concepts exposed by CodeGraph:
- directImpact;
- indirectImpact;
- affectedTests;
- summary.

It also accepts normalized symbols, steps, files, and tests so the Sazan impact contract remains provider-independent.

Provider wrappers are not part of the persisted schema.

## Privacy

For private/internal repositories:
- absolute file locations must not leak;
- when repository_root is supplied at runtime, persisted paths are made relative to that root;
- otherwise absolute private paths are replaced by opaque path hashes plus basename.

The normalizer operates on privacy-safe repository IDs from the C002 registry.

## Propagation model

### Local symbol/file impact
Local semantic evidence identifies files, tests, symbols, and process steps inside the changed repository.

### Contract impact
A change may explicitly identify one or more affected matched contract IDs.
Contract impact adds both provider and consumer repositories to review scope.

### Flow impact
If a changed symbol/step appears in a process flow, or an affected contract is bound to a flow edge:
- the flow is marked impacted;
- traversal begins at the earliest impacted point;
- downstream steps and repositories are added to blast radius.

Upstream repositories are not automatically marked merely because they precede the changed point.

## Compatibility

For contract version changes:
- wildcard/unspecified recorded requirements remain compatible;
- exact matching versions remain compatible;
- recorded mismatch becomes a critical compatibility finding.

## Impact levels

Deterministic baseline:
- critical — recorded version mismatch, or delete/version-change on a cross-repository contract with downstream impact;
- high — cross-repository contract/flow impact, or local breaking semantic impact;
- medium — downstream flow/repository impact or local warnings;
- low — mapped local-only change without warnings;
- unknown — insufficient mapping evidence.

These levels describe blast radius and review urgency, not business priority.

## Test/review scope

The output explicitly enumerates:
- repositories to review;
- contracts to validate;
- flows requiring end-to-end regression;
- local tests identified by semantic analysis.

## Incomplete evidence

A file change without local semantic evidence is flagged.
A change with no symbol, process, contract, file, or test mapping is marked partial-evidence.

The normalizer does not invent blast radius from filenames alone.

## Outputs

`scripts/diff_impact_normalize.py` produces:
- normalized JSON blast radius;
- Markdown review summary;
- compatibility findings;
- test/review scope;
- incomplete-evidence findings.
