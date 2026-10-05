# GitHub MCP integration

Status: implemented profile and launcher; live credentialed runtime proof is a separate gate.

## Purpose

SAZAN Autonomous Execution uses the official GitHub MCP Server as a governed execution provider. The default integration is intentionally read-only and fail-closed.

Canonical upstream:

- repository: `github/github-mcp-server`
- pinned release: `v1.14.0`
- container image: `ghcr.io/github/github-mcp-server:v1.14.0`

The pinned release was the current immutable GitHub release when this integration was reviewed on 2026-10-05.

## Default security posture

The launcher enforces:

- GitHub MCP read-only mode;
- GitHub MCP lockdown mode;
- an explicit toolset allowlist;
- no `all` toolset;
- no Git/Governance/Organization/Projects toolsets;
- disabled write authority;
- disabled destructive authority;
- token injection only at runtime;
- no token value in the Docker command or repository configuration.

Approved toolsets:

- `context`
- `repos`
- `pull_requests`
- `issues`
- `actions`
- `code_security`
- `secret_protection`

This is narrower than the full GitHub MCP surface.

## Token boundary

The launcher reads the secret from `SAZAN_GITHUB_TOKEN` and maps it into the container as `GITHUB_PERSONAL_ACCESS_TOKEN`.

Do not commit a token to this repository.

The credential itself must still follow least privilege. Read-only MCP mode limits the tools exposed by the server, but it does not replace GitHub-side credential scoping. Prefer a fine-grained credential or GitHub App installation limited to the required repositories and read permissions.

## Usage

Validate the profile and inspect the generated command without running the server:

```bash
python agents/repo-skill-steward/mcp/github_mcp_launcher.py --dry-run
```

Run the provider after supplying the secret through the runtime environment:

```bash
export SAZAN_GITHUB_TOKEN="<runtime-secret>"
python agents/repo-skill-steward/mcp/github_mcp_launcher.py
```

The launcher does not print the secret.

## Guardian boundary

This read-only provider is the baseline connection. Any future write-capable GitHub provider must be a separate profile and must pass SAZAN Guardian authorization before it is enabled.

A write-capable profile must never be created by silently changing this read-only profile.

## Runtime proof

Repository tests verify the configuration, pinning, allowlist, secret handling, and fail-closed behavior without requiring a real credential.

A production/runtime-ready claim additionally requires a credentialed proof against the intended deployment environment and verification that the exposed MCP tools match the approved read-only surface.
