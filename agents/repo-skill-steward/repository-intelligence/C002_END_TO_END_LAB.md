# C002 Realistic End-to-End Integration Lab

Context: C002
Date: 2026-09-30
Status: VERIFIED / PROMOTED

## Goal

Validate the promoted C002 Repository Intelligence controls as one realistic chain instead of isolated component labs.

## Scenario

The fixture models a four-repository checkout workspace:

- web consumes an HTTP checkout contract;
- api provides checkout and publishes an order-created event;
- contracts provides the shared checkout schema;
- a private worker consumes the order-created event and persists payment state.

The persisted outputs must not reveal the private repository source identity.

## End-to-end chain

1. Build the multi-repository registry and match contracts.
2. Synthesize one observed entry-to-terminal flow across repository boundaries.
3. Normalize an API event-publisher change and propagate downstream review impact.
4. Create an L2 cache entry and verify safe cross-revision reuse under unchanged semantic fingerprints.
5. Route providers with strict health checks while forcing Repomix unhealthy so the promoted Gitingest fallback is exercised.
6. Enforce strict stage budgets for context tokens, graph nodes, output bytes, and stage elapsed time.
7. Run the L0-L7 orchestrator in analysis mode.
8. Require the machine gate to stop at ready-for-parent-review with auto-promotion disabled.
9. Verify private repository source names are absent from all persisted lab outputs.

## Implementation

- scripts/run_c002_e2e_lab.py
- tests/test_repository_intelligence_e2e.py
- .github/workflows/repository-intelligence-c002-end-to-end-lab.yml

## Required success conditions

- registry status verified;
- exactly three matched internal contracts;
- one observed cross-repository flow;
- high diff-impact propagation from API to the private worker review boundary;
- provider fallback explicitly recorded;
- strict budget receipts recorded without violation;
- cross-revision cache hit only with stable fingerprints;
- orchestration reaches ready-for-parent-review;
- auto-promotion remains false;
- no private source identity leaks.

Status: VERIFIED — pull-request lab run 36764817135 passed the dedicated end-to-end tests, the C002 regression suite, the executable lab assertions, and the privacy-redaction checks.
