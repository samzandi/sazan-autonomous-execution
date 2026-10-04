# Release Checklist

A stable release may be considered only when the evidence-based release-readiness gate is green for the exact target commit.

## Required evidence

- [ ] Repository-wide CI is green.
- [ ] Core steward and repository-intelligence tests are green.
- [ ] Live Codex runtime proof is verified.
- [ ] Live Claude Code runtime proof is verified.
- [ ] Provider-parity evidence is verified.
- [ ] Failure and rollback evidence is verified.
- [ ] Reproducibility evidence is verified.
- [ ] Security and privacy review is complete.
- [ ] License and third-party attribution are reviewed.
- [ ] No unresolved release blockers remain.
- [ ] Release notes identify known limitations and rollback reference.

## Safety rule

A deterministic lab may verify the gate implementation, but it cannot substitute for a required live runtime proof. Missing credentials or quota remain explicit blockers rather than being bypassed.
