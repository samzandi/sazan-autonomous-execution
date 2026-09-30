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
Primary engine: CodeGraph Community 0.20.1
License: Apache-2.0
Baseline mode: graph-only
Evidence: semantic graph lab run 36740772666

Verified baseline:
- symbol discovery
- cross-file callers
- dependency relationships
- impact analysis
- digest-pinned binary execution
- telemetry-off operation
- MCP-compatible tool surface

Operational rule:
- query graph evidence before using text search to infer structural relationships;
- use text search as a fallback for literals, unsupported languages, missing graph evidence, or verification;
- keep Sazan graph schemas and orchestration engine-independent.

GitNexus remains benchmark/reference-only because its current PolyForm Noncommercial license is incompatible with embedding in Sazan commercial components.

Independent Sazan roadmap inspired by capability gaps:
- multi-repository registry
- cross-repository contracts
- process/execution-flow synthesis
- diff-to-impact normalization
- graph response token budgets
- graph-aware agent hooks
- optional PDG/control/data-flow and taint adapters

### L3 — Architecture Presentation
Primary renderer: Sazan deterministic Mermaid renderer
Input: normalized CodeGraph-style nodes and edges
Status: verified and promoted
Evidence: architecture presentation lab run 36742665729

Design:
- render locally with no API key and no network dependency;
- sanitize labels and use stable opaque node IDs;
- exclude external nodes by default;
- enforce node/edge budgets;
- keep the presentation adapter independent from the semantic graph provider;
- use GitHub-native Mermaid for repository documentation when appropriate.

GitDiagram remains optional/reference-only and is not a core dependency. Its hosted service and full self-hosted stack remain optional/reference-only because baseline operation requires additional cloud/storage/AI infrastructure. Use the hosted service only when richer interaction materially helps and repository privacy permits it.

### L4 — Wiki and Repository Q&A
Primary baseline: Sazan lightweight evidence-first Wiki/Q&A path
Status: verified and promoted
Evidence: Wiki/Q&A lab run 36744130393

Baseline components:
- CodeGraph architecture document generation;
- CodeGraph curated cross-codebase context;
- L1 context packers for supplemental text evidence;
- Sazan Mermaid renderer;
- active Sazan reasoning model for answer synthesis.

DeepWiki Open remains an optional self-hostable full Wiki/RAG product for persistent vector indexes, standalone wiki UI, codemap/guided tours, and long-lived conversational retrieval. It is not required by the core path.

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

No single upstream project is the Sazan engine. Sazan owns the orchestration, evidence model, policy gates, cross-repository identity, and cross-tool adapters.
