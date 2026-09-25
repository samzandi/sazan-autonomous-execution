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
