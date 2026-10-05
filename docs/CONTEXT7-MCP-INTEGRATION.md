# Context7 MCP integration

Status: governed read-only provider with live documentation proof.

## Selection

SAZAN uses the official Upstash Context7 MCP server for current library, framework, SDK, API, CLI, and cloud-service documentation.

The provider is pinned to:

- repository: `upstash/context7`
- package: `@upstash/context7-mcp@4.1.1`
- transport: `stdio`

The repository also ships `ctx7` CLI + Skills. That route is useful for coding agents that prefer concise CLI workflows, but SAZAN keeps MCP as the shared documentation provider because it exposes a stable two-tool interface to heterogeneous agents.

## Tool surface

The guarded default exposes exactly:

- `resolve-library-id`
- `query-docs`

Both upstream tools are annotated read-only. SAZAN still filters the upstream `tools/list` response and rejects any tool outside this explicit set.

## Data boundary

Context7 queries leave SAZAN and are sent to the Context7 service. Do not place secrets, access tokens, passwords, private keys, personal data, or proprietary source code in documentation queries.

The SAZAN proxy rejects common credential/key formats before forwarding a tool call and caps query length. This is a defense-in-depth filter, not a complete data-loss-prevention system.

## Credential boundary

A Context7 API key is optional for basic public usage and recommended upstream for higher rate limits.

If configured, SAZAN reads it only from `SAZAN_CONTEXT7_API_KEY` and maps it into the child process as `CONTEXT7_API_KEY`.

The child process receives a sanitized environment. Unrelated credentials such as GitHub, Vercel, Supabase, cloud, or deployment tokens are not intentionally forwarded.

The API key is never passed as a command-line argument.

## Telemetry

The local stdio provider runs with `OTEL_SDK_DISABLED=true` in the SAZAN profile. This keeps the provider focused on documentation retrieval and avoids opening the local embedded telemetry path.

## Validation

Static tests verify:

- canonical official source;
- exact package pin;
- stdio transport;
- exactly two approved tools;
- sanitized environment;
- no API key in command arguments;
- credential-like query blocking;
- Context7 library ID shape;
- tool inventory filtering.

The live workflow starts the real pinned package, completes MCP initialization, confirms the exact two-tool surface, resolves the official Next.js library, retrieves current Next.js documentation, and confirms that a credential-like query is blocked locally.
