# C002 Diff → Impact Normalization

Context: C002
Date: 2026-09-30
Status: LAB VALIDATION

## Purpose

Translate repository changes into an evidence-backed cross-repository blast radius without guessing impact from filenames, naming conventions, or a synthetic numeric risk score.

## Inputs

The normalizer consumes:
- privacy-safe multi-repository registry;
- matched contract graph;
- synthesized process/execution flows;
- normalized change observations;
- local semantic-impact evidence when the changed surface is a file or symbol.

## Change surfaces

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

Change types:
- add;
- modify;
- delete;
- rename;
- version-change.

## Local semantic impact

File/symbol changes should carry local semantic-impact evidence produced by tools such as CodeGraph.

Supported mappings:
- impacted process-step IDs;
- impacted symbol names;
- evidence references.

A filename alone is not sufficient to claim downstream impact.

## Contract impact

API/event/schema/package/etc. changes bind to a concrete matched contract ID.

The normalizer then:
- marks both contract parties for review;
- locates process-flow edges using that contract;
- propagates downstream impact through complete runtime flows;
- records affected flows and factual test/review scope.

For version-change observations, the new provider version is compared with the recorded consumer requirement.
A mismatch is reported as a compatibility finding. It is not silently converted into a claim that runtime breakage has already occurred.

## Blast radius

Output categories:
- directly and transitively affected process steps;
- affected contracts;
- affected end-to-end flows;
- repositories requiring review/testing;
- compatibility findings;
- incomplete evidence.

For a local step change, downstream propagation begins at the earliest affected point in each flow.
For a contract change, both contract participants plus the runtime path from the contract hop onward are included.

## Evidence semantics

Each change is OBSERVED or INFERRED.
Inferred changes require rationale.

If a file/symbol change cannot be mapped to semantic symbols/steps, the report becomes `partial-evidence`.
A file change without local semantic-impact evidence also produces `partial-evidence`.

This prevents an unknown blast radius from being presented as complete.

## Test/review scope

The normalizer emits factual review targets:
- impacted repositories;
- touched contracts;
- impacted end-to-end flows.

It does not assign speculative numeric risk scores.

## Privacy

The layer operates entirely on privacy-safe repository IDs and never requires private repository source names.
