# Sazan Repository Intelligence

## Purpose

Provide evidence-driven repository understanding for the parent Sazan Repo & Skill Steward.

## Trigger

Use when a repository must be evaluated, reverse engineered, compared, documented, or prepared for safe capability extraction.

## C002 orchestration

For end-to-end runs, use `scripts/orchestrate_repository_intelligence.py` as the control entry point and the common evidence-envelope contract for stage handoff.

Rules:
- preserve L0→L7 ordering;
- analysis-only runs skip semantic editing;
- stop on blocked/failed stages;
- respect run budgets;
- redact private/internal repository identities from persisted public artifacts;
- delegate L7 policy to the verified promotion gate;
- never auto-promote.

## Multi-repository workspace

When analysis spans more than one repository:
- build the workspace with `scripts/multi_repo_registry.py`;
- require stable repository identity before cross-repo reasoning;
- model contracts as evidence-backed `provides` and `requires` observations;
- block unresolved internal contracts, ambiguous providers, and incompatible versions;
- preserve inferred-contract constraints;
- never persist private/internal repository source names;
- keep external dependencies external unless evidence shows an internal provider.

## Process / execution flows

For cross-repository runtime analysis:
- synthesize flows with `scripts/process_flow_synthesis.py`;
- use only registry-backed repository IDs;
- allow cross-repository hops only through matched contracts;
- require explicit runtime direction for each contract binding;
- aggregate evidence across local and cross-repository hops;
- downgrade the full path when any hop is inferred;
- enforce max-hop and max-path budgets;
- report cycles and unreachable steps rather than silently dropping them.

## Diff → impact

For change-impact analysis:
- use CodeGraph 0.20.1 `codegraph_pr_context` for repository-local git-diff evidence;
- use `codegraph_analyze_impact` for focused single-symbol impact when needed;
- normalize with `scripts/diff_impact_normalize.py`;
- map changed artifacts explicitly to process steps and contract sides;
- propagate provider-side contract changes to consumers;
- identify downstream repositories through verified process flows;
- preserve local related-test evidence;
- keep risk separate from observed/inferred confidence;
- never include private repository source names in impact artifacts.

## Required stages

1. Intake
   - Record canonical repository, revision, source, visibility class, and requested purpose.
   - Never persist private repository names in this public repository.

2. Context build
   - Prefer Repomix for full/filtered context packing.
   - Use Gitingest for lightweight remote digest.
   - Use Code2Prompt when a scoped, templated, agent-oriented prompt is more efficient.

3. Structure and semantics
   - Build semantic dependency evidence with CodeGraph Community (Apache-2.0).
   - Query graph relationships before inferring them from raw text.
   - Do not treat text packing as a substitute for dependency/call analysis.

4. Documentation, visualization, and Q&A
   - Use CodeGraph architecture-doc generation for the baseline wiki seed.
   - Use CodeGraph curated context for natural-language repository questions.
   - Use the internal Sazan Mermaid renderer for baseline diagrams.
   - Add L1 packed text context only when graph evidence is insufficient.
   - Use DeepWiki Open only as an optional full Wiki/RAG product when persistent vector retrieval or a standalone wiki UI is required.
   - Never send private repository content to an external hosted wiki/Q&A service by default.

5. Semantic editing
   - Use CodeGraph impact evidence before high-connectivity edits.
   - Prefer symbol-aware rename/edit/delete over regex-based identifier surgery.
   - Primary provider is pinned Serena 1.7.0 (MIT), never an unpinned Serena install.
   - Run Serena through an isolated MCP/subprocess boundary; do not embed its headless application runtime in the primary Sazan process.
   - Keep current Serena v2 GPL application code outside the Sazan commercial core unless separately approved.
   - Re-run diagnostics/tests and CodeGraph verification after edits.
   - Never perform semantic edits directly on the protected default branch.

6. License and security gate
   - Verify license from the canonical source before integration.
   - Detect install scripts, secrets access, network calls, binary downloads, privileged operations, workflow mutations, and unsafe shell execution.
   - Unknown license means reference-only.
   - Non-commercial license means no embedded use in Sazan commercial core.

7. Capability extraction
   - Extract concepts, interfaces, algorithms, tests, UX patterns, and architectural techniques.
   - Prefer reimplementation from documented behavior when copying code would create licensing or coupling risk.

8. Reverse engineering
   - Route rebuild work through the Reverse Engineering sub-agent.
   - Build a clean-room specification from evidence produced by earlier layers.
   - Classify each material claim as observed, inferred, or unknown.
   - Observed claims require evidence IDs; inferred claims require evidence plus rationale.
   - Require acceptance criteria and preserve unresolved questions.
   - GitReverse is reference-only and must not be treated as authoritative reconstruction evidence.

9. Verification
   - Require source citations/evidence, reproducible checks, and a rollback path.
   - Compare claims against repository code or canonical documentation.
   - The verifier must reject unsupported observed claims and hidden assumptions.

10. Output
   - Produce an evidence package with: purpose, architecture, dependencies, license, security notes, strengths, limitations, reusable capabilities, rejected items, rebuild specification, evidence ledger, and recommended next action.

## Promotion rule

Repository Intelligence may propose; the parent Repo & Skill Steward decides promotion.
The L7 promotion gate must evaluate provenance, license, security, lab evidence, capability delta, rollback, private-data handling, and verifier state.
The automated result may be eligible-for-parent-promotion, eligible-with-constraints, pending-evidence, or rejected.
Auto-promotion is forbidden.
No evidence = no promotion.
