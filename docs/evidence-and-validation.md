# Evidence and Validation

## Principle

No evidence = not done.

## Evidence hierarchy

Prefer the strongest available evidence:

1. authoritative system state after the action;
2. automated test/build/check output;
3. re-read/re-fetch of the modified artifact;
4. deterministic comparison against acceptance criteria;
5. documented manual inspection when automation is unavailable.

## Material action gate

After a material action:

- identify the expected observable outcome;
- inspect that outcome;
- record pass/fail evidence;
- recover and retry on failure when safe.

## Completion gate

Before COMPLETE, verify:

- final goal is satisfied;
- planned acceptance criteria are covered;
- critical outputs were re-checked;
- known failures are resolved or explicitly blocked/out of scope;
- no unsupported production-ready claim is made.

## Production-ready gate

Production-ready requires concrete end-to-end evidence appropriate to the project, such as successful tests/builds, deployment/health verification, security/quality gates, or authoritative system checks. Documentation existence alone is insufficient.
