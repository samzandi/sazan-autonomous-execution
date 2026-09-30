# Sazan Repository Intelligence Architecture

Context: C001
Date: 2026-09-30
Status: ACTIVE

## Layer model

### L0 — Intake
Owner: intake sub-agent
Output: canonical source, revision, visibility class, scope, provenance.

### L1 — Context Packaging
Primary: Repomix
Fallback: Gitingest
Scoped/templated: Code2Prompt

Rationale:
- Repomix provides remote repository processing, token-aware packing, git-aware context, configurable filtering, and security checks.
- Gitingest is lightweight, Python-native, and convenient for URL-to-digest workflows.
- Code2Prompt adds fast Rust-based context engineering, templates, Python SDK, MCP support, and an agent skill.

### L2 — Semantic Graph
Preferred candidate: CodeGraph

Requirements:
- symbols
- imports
- references
- call chains
- dependency/dependent relationships
- impact analysis
- persistent graph state
- MCP exposure

GitNexus is used only as a benchmark/reference architecture while its non-commercial license remains incompatible with embedded commercial use.

### L3 — Architecture Presentation
Primary visual candidate: GitDiagram
Secondary: generated Mermaid/graph views from L2.

### L4 — Wiki and Repository Q&A
Primary candidate: DeepWiki Open.
ExplainGitHub remains an external reference until its implementation and license are auditable.

### L5 — Semantic Editing
Optional external adapter: Serena.

Integration rule:
- Treat Serena as a separately operated tool/service.
- Do not vendor current GPL application code into the Sazan core without a deliberate licensing review.
- Prefer stable protocol boundaries such as MCP.

### L6 — Reverse Engineering
GitReverse can generate a synthetic build prompt, but it is not a substitute for architecture analysis.
Until its license is verified, keep it reference-only.

### L7 — Evidence and Promotion
Owner: verifier sub-agent + parent Repo & Skill Steward.

Promotion requires:
- canonical provenance
- license compatibility
- security review
- reproducible lab evidence
- explicit capability delta
- rollback path

## Data flow

Repository
  -> Intake
  -> Context Pack
  -> Semantic Graph
  -> Architecture/Wiki
  -> License & Security
  -> Capability Extraction
  -> Reverse-Engineering Hypothesis
  -> Verification
  -> Parent Steward Promotion Gate

## Design rule

No single upstream project is the Sazan engine. Sazan owns the orchestration, evidence model, policy gates, and cross-tool adapters.
