# Sazan Repository Intelligence Architecture

Context: C001
Date: 2026-09-30
Status: ARCHIVE — baseline architecture complete

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
Primary candidate: Serena 1.7.0 pinned to immutable commit 949a27ef1e5fda1a6e7b561e777bcece345c6ffd
License: MIT
Status: verified and promoted as isolated provider
Evidence: semantic editing lab run 36745934710

Guard model:
- CodeGraph impact analysis before edits;
- Serena symbol/reference-aware edit on an isolated branch/worktree;
- tests/diagnostics after edit;
- CodeGraph re-index and post-edit verification;
- rollback point recorded before destructive mutation.

Serena v2/current application code is GPL-3.0-or-later and is not part of the Sazan commercial core. It remains external/reference-only unless a separate licensing decision is made.

Operational boundary:
- run Serena 1.7.0 as an isolated MCP/subprocess provider, not inside the primary Sazan process;
- CodeGraph remains the pre/post edit safety gate;
- direct default-branch edits remain prohibited.

SolidLSP remains MIT and is a future candidate for a Sazan-owned semantic editing engine if long-term independence from the frozen Serena 1.7 adapter becomes valuable.

### L6 — Reverse Engineering
Primary: Sazan clean-room rebuild specification
Owner: reverse-engineering sub-agent
Status: verified and promoted
Evidence: reverse engineering lab run 36747513165

Inputs:
- provenance from L0;
- packed context from L1;
- semantic graph evidence from L2;
- architecture views from L3;
- repository Q&A and architecture docs from L4;
- runtime/test and edit-impact evidence from L5 when relevant;
- license/security findings.

Output:
- deterministic REBUILD_SPEC.md;
- normalized rebuild-spec.json;
- evidence ledger;
- explicit OBSERVED / INFERRED / UNKNOWN claim states;
- acceptance criteria;
- clean-room constraints and unresolved questions.

GitReverse remains reference-only. Its quick flow reconstructs a short synthetic user prompt primarily from repository metadata, a depth-1 file tree, and README context. No root license file or detected GitHub license was found in the current review, and the shallow prompt output is not authoritative enough for Sazan rebuild work.

Operational rule:
- every observed claim must cite evidence;
- every inferred claim must cite evidence and provide rationale;
- unknowns must remain explicit;
- verifier approval is required before promotion.

### L7 — Evidence and Promotion
Primary engine: Sazan deterministic promotion gate
Owner: verifier sub-agent + parent Repo & Skill Steward
Status: verified and promoted
Evidence: promotion gate lab run 36748478777

Mandatory evidence:
- canonical provenance and immutable revision;
- license compatibility evaluated against integration mode;
- security review;
- reproducible lab evidence when executable behavior is involved;
- explicit capability delta;
- verified rollback path;
- private-data handling status;
- verifier decision with evidence.

Machine decisions:
- eligible-for-parent-promotion;
- eligible-with-constraints;
- pending-evidence;
- rejected.

Hard rule:
- the gate never auto-promotes;
- eligible means only eligible for final parent steward approval;
- unknown license may only be carried as constrained reference-only evidence;
- non-commercial licensing is reference-only, never commercial-core integration.

## Data flow

Repository
  -> Intake
  -> Context Pack
  -> Semantic Graph
  -> Architecture/Wiki
  -> License & Security
  -> Capability Extraction
  -> Clean-room Rebuild Specification
  -> Verification
  -> Parent Steward Promotion Gate

## Design rule

No single upstream project is the Sazan engine. Sazan owns the orchestration, evidence model, policy gates, cross-repository identity, and cross-tool adapters.
