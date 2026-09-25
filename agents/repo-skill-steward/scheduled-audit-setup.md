# Scheduled Account Audit Setup

The scheduled audit is designed to inspect all repositories available to a dedicated GitHub credential while keeping private repository identities out of public workflow summaries.

## Current behavior

- Runs daily at 03:17 UTC and can also be started manually.
- Is read-only.
- Does nothing to private repositories until a repository secret named STEWARD_GITHUB_TOKEN exists.
- If the secret is missing, the workflow exits safely after writing a credential-status note.
- When configured, inventory is generated with --public-safe before any report is rendered.

## Recommended credential for the read-only phase

Use a dedicated fine-grained GitHub personal access token rather than a broad classic token.

Repository access:
- Select the repositories the Steward is allowed to inspect.

Repository permissions:
- Metadata: read.
- Contents: read.
- Actions: read only if future workflow-health inspection requires it.

Do not grant write permissions for the scheduled read-only audit.

Store the credential in the sazan-autonomous-execution repository as an Actions secret named:

STEWARD_GITHUB_TOKEN

## Future write phase

Creating update branches or pull requests across repositories is intentionally separate. That phase should use a dedicated GitHub App or a separate fine-grained token with narrowly scoped write permissions. The read-only token should not be silently upgraded.
