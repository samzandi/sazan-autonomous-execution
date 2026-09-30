# C002 Multi-Repository Registry and Contract Graph

Context: C002
Date: 2026-09-30
Status: VERIFIED

Verified lab run: 36751884638

Verified:
- four repositories registered in one workspace;
- three internal contracts matched;
- one external requirement remained external without blocking;
- private repository source identity did not appear in persisted output;
- deliberate version mismatch blocked the workspace;
- ambiguous provider handling and provider hints were validated;
- inferred relationships propagated constraints;
- malformed contract observations were rejected;
- contract identifiers include provider, consumer, key, and kind;
- deterministic output was verified.

## Purpose

Give Repository Intelligence a stable workspace-level view across multiple repositories without leaking private repository identities.

## Registry identity

Public/local-fixture repositories:
- canonical source may be persisted;
- repository_id may be explicit or derived deterministically from the canonical source.

Private/internal repositories:
- must provide a stable opaque repository_id;
- the persisted registry never contains the private source name;
- the opaque ID must remain stable across revisions so cross-repository history can be compared.

## Contract observations

Each repository can declare evidence-backed observations in two directions:

- provides — interfaces the repository exposes;
- requires — interfaces the repository consumes.

Supported baseline kinds:
- http-api
- event
- schema
- package
- cli
- storage
- custom

Every observation must include evidence.
Inferred observations additionally require rationale.

## Matching

A cross-repository contract is formed when:
- contract key and kind match;
- a single provider is resolved;
- provider and consumer are different repositories;
- versions are compatible.

Baseline version compatibility is deliberately strict:
- exact version match; or
- consumer requirement is wildcard/unspecified.

Future semantic version-range resolution can be added behind the same contract model.

## Blockers

The baseline registry blocks on:
- unresolved internal contract;
- ambiguous provider;
- version mismatch;
- self-contract incorrectly modeled as cross-repository.

External requirements are recorded but do not require an internal provider.

## Outputs

`scripts/multi_repo_registry.py` produces:
- registry.json — repositories plus upstream/downstream topology;
- contracts.json — matched contracts, external requirements, blockers, and summary.

## Privacy boundary

Private/internal source strings are runtime-only inputs.
They must not appear in persisted registry or contract outputs.
