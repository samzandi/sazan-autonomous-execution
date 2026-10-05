# Playwright MCP integration

Status: governed observe-mode provider with live browser proof.

## Selection

SAZAN uses the official Microsoft Playwright MCP server for persistent browser sessions and iterative browser reasoning.

The official Playwright CLI remains the preferred alternative for high-throughput coding-agent workflows where token efficiency matters more than persistent MCP state. It is not a replacement for the persistent browser provider.

Reviewed releases on 2026-10-05:

- Playwright MCP: `microsoft/playwright-mcp` at `v0.0.83`
- Playwright CLI alternative: `microsoft/playwright-cli` at `v0.1.22`

## Security boundary

Microsoft explicitly documents that Playwright MCP itself is not a security boundary. SAZAN therefore does not expose the upstream server directly.

The default SAZAN provider is a stdio guard proxy. It filters `tools/list`, rejects unapproved `tools/call` requests before they reach Playwright MCP, and applies URL policy to navigation/network-read calls.

Default observe tools:

- `browser_console_messages`
- `browser_find`
- `browser_navigate`
- `browser_network_request`
- `browser_network_requests`
- `browser_snapshot`
- `browser_take_screenshot` without explicit file output
- `browser_get_config`
- read-only cookie/localStorage/sessionStorage inspection

Explicitly unavailable by default include clicking, typing, form filling, uploads, arbitrary page evaluation, unsafe code execution, route mutation, storage mutation, coordinate controls, PDF/devtools/vision/testing capabilities, and browser profile persistence.

## Runtime isolation

The provider is pinned to `@playwright/mcp@0.0.83` and starts with:

- headless browser;
- isolated in-memory browser state;
- Chromium/Chrome channel;
- browser sandbox enabled;
- WebMCP disabled;
- service workers blocked;
- image responses omitted;
- code generation disabled;
- optional capability sets disabled;
- bounded output size;
- bounded action/navigation/idle timeouts;
- temporary output directory.

The normal profile blocks localhost, loopback, link-local, private, reserved, multicast, and unspecified network targets. This reduces SSRF exposure. The live smoke workflow enables a temporary localhost override only for its self-contained test server.

## Action mode

The observe profile must not be silently widened.

Interactive actions such as click, type, upload, submit, account modification, purchase, deletion, or other consequential browser operations require a separate action-capable profile and Guardian authorization. Destructive or externally consequential actions also require the applicable human-confirmation gate.

## Validation

Static tests verify pinning, isolation flags, capability restrictions, tool filtering, file-output restrictions, and private-network denial.

The live workflow launches the real pinned Playwright MCP package, navigates a real headless Chrome instance to an ephemeral local test page, verifies an accessibility snapshot, and confirms that `browser_click` is blocked by the SAZAN proxy.
