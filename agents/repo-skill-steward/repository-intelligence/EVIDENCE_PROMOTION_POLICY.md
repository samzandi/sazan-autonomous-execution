# Evidence and Promotion Policy

Context: C001
Date: 2026-09-30
Status: VERIFIED

Verified lab run: 36748478777

Verified:
- twelve promotion-policy unit tests passed;
- a fully evidenced candidate was eligible but remained non-automatic;
- unknown-license core integration was blocked as pending evidence;
- unknown-license reference-only handling preserved a no-copy constraint;
- non-commercial core integration was rejected;
- verifier constraints propagated to the final result;
- provenance, security, lab, capability delta, rollback, private-data, and verifier gates were all exercised.

## Purpose

Make promotion a reproducible policy decision instead of an informal judgment.

## Authority model

- Repository Intelligence may discover, analyze, test, and propose.
- The Verifier sub-agent may block promotion.
- The automated gate may declare a candidate eligible, constrained, pending, or rejected.
- The automated gate never promotes by itself.
- Final promotion authority remains with the parent Repo & Skill Steward.

## Mandatory gates

Every promotion package must contain:
1. canonical provenance and immutable revision;
2. license status and canonical evidence;
3. security review and evidence;
4. reproducible lab evidence when executable behavior is involved;
5. explicit capability delta versus the current Sazan stack;
6. verified rollback path;
7. private-data handling status;
8. verifier decision and evidence.

## Decisions

### eligible-for-parent-promotion
All mandatory gates passed and no additional constraint is recorded.

### eligible-with-constraints
All mandatory gates passed, but the security review, verifier, or package records explicit operating constraints.

### pending-evidence
One or more required gates are incomplete or unknown.

### rejected
A hard blocker exists, including:
- incompatible license;
- non-commercial license proposed for embedded/internal commercial-core use;
- failed security review;
- failed lab;
- private-data policy violation;
- incompatible capability delta;
- duplicate core capability without a replacement rationale;
- verifier rejection.

## Integration modes

- embedded-core
- internal-component
- external-adapter
- reference-only

License compatibility is evaluated against the proposed integration mode, not only the existence of a license.

## No automatic promotion

The machine-readable result always sets auto_promote to false.
An eligible result means only that the candidate may be presented to the parent steward for the final promotion decision.

## Evidence retention

Promotion evidence must preserve:
- candidate identity;
- revision;
- decision;
- check states;
- constraints;
- test/run references;
- rollback strategy.

Private repository names or private code must not be committed into this public repository.
