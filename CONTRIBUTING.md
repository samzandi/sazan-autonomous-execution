# Contributing

Sazan Autonomous Execution welcomes focused, verifiable contributions.

## Contribution requirements

- Open or reference an issue for substantial work.
- Keep scope bounded and preserve fail-closed behavior.
- Add tests for behavior changes.
- Run the relevant unit and integration checks.
- Document security, privacy, rollback, and evidence implications.
- Never commit secrets, private repository inventories, customer data, or credentials.
- Do not weaken human-authorization boundaries to make a test pass.

## Pull requests

A pull request should state the problem, intended behavior, non-goals, verification evidence, failure behavior, and known limitations. Runtime-provider claims must include real runtime evidence; deterministic simulations are not a substitute.

## Review standard

Maintainers may reject changes that broaden permissions, hide blockers, manufacture evidence, or make release-readiness claims that are not supported by reproducible checks.
