# C002 Provider Health and Fallback Controls

Context: C002
Date: 2026-09-30
Status: LAB VALIDATION

## Purpose

Make provider selection explicit, evidence-backed, and fail-closed.

The provider router separates three questions:
- Is a provider healthy?
- Is the provider eligible for this stage contract?
- Is fallback from the primary provider explicitly permitted?

A healthy provider is not automatically eligible for every stage.

## Implementation

Primary implementation:
scripts/provider_health.py

## Health observations

Supported states:
- healthy
- degraded
- unhealthy
- unknown

Every observation requires evidence.

No observation means the provider is not eligible in strict routing.

Degraded providers are not selected unless degraded operation is explicitly allowed for the run.

## Stage contracts

Each stage route declares:
- an ordered candidate list;
- the stage capability contract;
- whether the candidate is approved for private/internal targets.

A fallback candidate must satisfy the same capability contract as the primary provider.

The baseline automatic fallback is intentionally narrow:
- L1 context packaging: Repomix -> Gitingest.

Code2Prompt remains a scoped agent/MCP path, not a silent full-context fallback.

Stages without an equivalent promoted fallback fail closed when their primary provider is unavailable.

## Private/internal repositories

For private or internal targets, a candidate must be marked private-safe.

A healthy provider that is not private-safe is rejected.

## Fallback receipts

Each routing decision records:
- primary provider;
- selected provider;
- capability contract;
- health evidence;
- attempted candidates and reasons;
- whether fallback was used;
- constraints or blockers.

Fallback is never silent.

## Failure semantics

The route is blocked when:
- no health observation exists for all eligible candidates;
- all eligible candidates are unhealthy/unknown;
- degraded health is not explicitly permitted;
- a fallback candidate does not satisfy the primary stage contract;
- a private/internal target would require a non-private-safe provider.

## Orchestration boundary

Provider routing does not weaken:
- budget enforcement;
- license/security gates;
- parent promotion authority.

A fallback provider must still produce the same evidence-envelope contract and pass all downstream gates.
