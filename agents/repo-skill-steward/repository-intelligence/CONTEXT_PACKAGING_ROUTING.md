# Context Packaging Routing Policy

Context: C001
Date: 2026-09-30
Status: VERIFIED

## Decision

Use a three-path context packaging layer instead of selecting one tool for every repository task.

### Repomix — default full-context packer

Pinned version: 1.18.1
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

Pinned version: 4.2.0
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

Operational constraint:
- treat Code2Prompt's gitignore behavior as repository-context behavior;
- the lab observed an ignored file included when the same fixture was only a plain directory;
- after the fixture was initialized as a Git repository, the ignored file was correctly excluded.

### Gitingest — lightweight Python fallback

Pinned version: 0.3.1
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

## Canonical evidence

- All three canonical repositories declare MIT licensing.
- Repomix 1.18.1 was released on 2026-09-21.
- Gitingest 0.3.1 was released on 2025-07-31.
- Code2Prompt 4.2.0 was released on 2025-12-11.
- All three repositories showed recent repository activity when checked on 2026-09-30.
- Repomix documents token counting, Secretlint-backed secret detection, Tree-sitter compression, remote repository support, git-aware filtering, and multiple output formats.
- Code2Prompt documents CLI/TUI, Python SDK, MCP operation, template-driven context generation, token estimation, smart file reading, and git integration.
- Gitingest documents CLI, sync/async Python APIs, URL ingestion, private-repository token support, submodule support, gitignore behavior, and Docker self-hosting.

## Lab evidence

Workflow: Repository Intelligence Context Packaging Lab
Successful run: 36739897813
Fixture: initialized Git repository containing Python, TypeScript, Markdown, JSON, and one gitignored file.

Verified:
- all three pinned tools processed the same fixture;
- all three produced non-empty output;
- all three excluded the gitignored marker when run against the Git repository;
- no user secrets were provided;
- workflow repository permission was contents: read;
- the Code2Prompt Linux binary matched its canonical SHA-256 release digest.

Observed on that single GitHub-hosted runner:
- Code2Prompt: 827 bytes, 59 lines, 52 ms;
- Gitingest: 1281 bytes, 53 lines, 1250 ms;
- Repomix: 2277 bytes, 86 lines, 6186 ms.

These runtime and size measurements are fixture-specific observations. They are not general performance rankings because startup, packaging format, runtime implementation, caches, and package resolution differ.

## Promotion states

- Repomix: promoted as default full-context packer.
- Code2Prompt: promoted as scoped agent/MCP context path, with the Git-repository constraint documented above.
- Gitingest: promoted as lightweight Python fallback.
