# Repository Update Matrix

The Repo & Skill Steward classifies repositories dynamically instead of keeping a static inventory of private projects in this public repository.

## Update strategies

| Strategy | Trigger | Default action |
| --- | --- | --- |
| upstream-sync | Repository is a real fork with a verified parent/source | Compare first; preserve local commits; propose a PR only when upstream is ahead |
| dependency-update | A supported dependency manifest is present | Detect candidate updates; test before promotion |
| container-image-update | Compose or Docker image configuration is present | Check image tags and release notes; lab test before deployment |
| github-actions-update | GitHub Actions workflows are present | Check action revisions; pin trusted actions; run repository CI |
| skill-agent-audit | Skill or agent surfaces are present | Check provenance, overlap, integrity, license, and runtime fit |
| monitor-only | No safe automated update surface is detected | Observe changes; do not mutate |

## Verification profiles

- ci-and-tests: update proposals may be generated automatically, but never auto-merged.
- tests-plus-manual-review: local tests exist but CI is missing; require manual review before promotion.
- manual-review-first: update surface exists but tests are missing; do not auto-propose production promotion.
- monitor-only: no update automation is selected.

## Current public-repository snapshot

This snapshot intentionally names only public repositories. Private repositories are classified at runtime and are never committed here.

- Sam-: monitor-only until project content exists.
- issue-driven-ai-development: skill-agent-audit; manual verification is required because repository-native tests/CI are not present.
- sazan-quickstarts: github-actions-update plus skill-agent-audit; repository validation workflows provide a verification path.
- ponytail: upstream-sync, github-actions-update, and skill-agent-audit. At the 2026-09-25 audit the fork was not behind upstream and had one local AGENTS.md change to preserve.
- sazan-seo-engine: skill-agent-audit; automated validation is a known gap.
- sazan-autonomous-execution: skill-agent-audit; the Repo & Skill Steward feature branch adds CI for its own module.
- Sazan-Efficient-Operator: skill-agent-audit; manual verification remains required until repository-native tests/CI exist.
- sazan-ai-automation: container-image-update; production promotion requires deployment/runtime validation and must not be inferred from a Compose edit alone.

## Private repository policy

Private repositories are inspected dynamically through authenticated GitHub access. Public-safe output contains only aggregate capability flags and counts, never private names, workflow names, branches, dependency filenames, URLs, descriptions, or upstream identities.

## Promotion invariant

The steward can discover and propose updates. It never auto-merges. Every promoted update needs evidence, project-specific verification, and a rollback path.
