# Context Packaging Routing Policy

Context: C001
Date: 2026-09-30
Status: LAB VALIDATION

## Decision

Use a three-path context packaging layer instead of selecting one tool for every repository task.

### Repomix — default full-context packer

Pinned evaluation version: 1.18.1
License: MIT

Route to Repomix when the task needs:
- full repository packaging;
- token-aware output;
- configurable include/exclude rules;
- git-aware context;
- optional code compression;
- built-in secret-pattern filtering;
- remote repository processing;
- Markdown, XML, JSON, or plain-text packaging.

### Code2Prompt — scoped agent context path

Pinned evaluation version: 4.2.0
License: MIT

Route to Code2Prompt when the task needs:
- agent-driven scoped context gathering;
- template-driven prompt construction;
- Python SDK integration;
- MCP-based access;
- fast Rust-native traversal;
- git diff/log context;
- interactive or targeted context generation.

The Linux release binary used by the lab is digest-pinned:
SHA-256: 69ff91f6e690de4814f38eb79d1fff5971d5a39bdc82b23ea784dcd450bf965f

### Gitingest — lightweight Python fallback

Pinned evaluation version: 0.3.1
License: MIT

Route to Gitingest when the task needs:
- a simple URL/directory-to-digest path;
- Python-native embedding;
- asynchronous Python use;
- straightforward self-hosting;
- a lightweight fallback when richer context engineering is unnecessary.

## Routing order

1. Start with Repomix for general repository intake.
2. Switch to Code2Prompt when an agent needs dynamic, scoped, templated context or MCP access.
3. Use Gitingest when Python-native simplicity or a lightweight digest is the priority.
4. Do not run all three by default. Parallel execution is reserved for validation, regression testing, or ambiguous cases.

## Evidence available before runtime lab

- All three canonical repositories declare MIT licensing.
- Repomix 1.18.1 was released on 2026-09-21.
- Gitingest 0.3.1 was released on 2025-07-31.
- Code2Prompt 4.2.0 was released on 2025-12-11.
- All three repositories showed recent repository activity when checked on 2026-09-30.
- Repomix documents token counting, Secretlint-backed secret detection, Tree-sitter compression, remote repository support, git-aware filtering, and multiple output formats.
- Code2Prompt documents CLI/TUI, Python SDK, MCP operation, template-driven context generation, token estimation, smart file reading, and git integration.
- Gitingest documents CLI, sync/async Python APIs, URL ingestion, private-repository token support, submodule support, gitignore behavior, and Docker self-hosting.

## Lab gate

The isolated GitHub Actions lab must verify:
- all three pinned tools can process the same mixed-language fixture;
- each produces a non-empty output;
- each respects the fixture's gitignore rule;
- no secrets are provided to the workflow;
- repository permissions remain read-only;
- the Code2Prompt release digest matches the canonical GitHub release digest.

Runtime speed and output size are recorded as observations, not universal performance claims.

## Promotion states

- Repomix: proposed-primary, pending-lab
- Code2Prompt: proposed-scoped-agent-path, pending-lab
- Gitingest: proposed-lightweight-fallback, pending-lab
