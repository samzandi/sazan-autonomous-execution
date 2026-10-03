# Sazan Repo & Skill Steward

This module extends Sazan Autonomous Execution with repository maintenance and skill/agent lifecycle management.

## Pipeline

Inventory -> Discover -> Triage -> Security Gate -> Lab -> Verify -> Pull Request -> Promote -> Document

## Design principles

- Private repository inventory is discovered dynamically and is not stored in this public repository.
- New skills and agents are treated as untrusted until reviewed.
- Updates are repository-specific, not globally forced.
- Project labs are used for experiments before integration.
- Pull requests are preferred for material changes.
- Rollback information is mandatory for promoted updates.
- Shared frontend tooling is deduplicated before installation and pinned to canonical upstream sources.

## Shared frontend design stack

The canonical UI stack is defined in `frontend-design-stack.yml`.

Its default flow is:

Anthropic Frontend Design -> selected Taste Skill specialists -> project DESIGN.md -> Vercel Web Design Guidelines -> Playwright CLI verification.

Awesome Design MD is reference-only. Image-to-code is consumed from Taste Skill rather than installed as a duplicate standalone skill.

Use `frontend-quality-gate.md` for acceptance criteria and `templates/SAZAN_UI_DESIGN_BRIEF.md` when bootstrapping a project-specific design contract.

## Initial integration targets

The steward is intended to coordinate with:

- Sazan Autonomous Execution for continuation and recovery.
- Sazan Efficient Operator for execution efficiency.
- project-specific labs such as ReViva Lab.
- repository-native CI for verification.
- dependency update tooling such as Renovate when appropriate.

## Next implementation slice

1. Dynamic GitHub repository inventory.
2. Repository classification rules.
3. Upstream/fork drift detection.
4. Dependency update detection.
5. Skill/agent candidate scoring.
6. Security inspection checklist.
7. Lab runner adapters.
8. Pull-request report generation.
9. Frontend design stack candidate lab and cross-project rollout.
