# Sazan Repository Intelligence Engine

Status: C001 ARCHIVE — baseline complete; C002 ACTIVE
Date: 2026-09-30
Parent: Sazan Repo & Skill Steward

## Mission

Turn an external or internal repository into a structured evidence package that Sazan agents can understand, compare, test, and safely promote without blindly copying upstream code.

## C002 orchestration

The C002 entry point is `scripts/orchestrate_repository_intelligence.py`, backed by a common evidence envelope. It coordinates the verified L0–L7 layers while preserving private-repository identity rules, explicit run budgets, and the parent steward promotion boundary.

## Multi-repository workspace layer

C002 adds `scripts/multi_repo_registry.py` for stable repository identity, upstream/downstream topology, and evidence-backed cross-repository contracts. Private/internal repositories use opaque stable IDs; their source names are excluded from persisted registry output.

## Cross-repository execution flows

C002 adds `scripts/process_flow_synthesis.py` to reconstruct bounded, evidence-backed runtime paths across repositories. Repository boundaries can only be crossed through matched contracts, and each cross-repository hop declares its runtime direction explicitly.

## Diff → impact layer

C002 uses `scripts/diff_impact_normalizer.py` to combine provider-backed local semantic evidence with cross-repository contracts and execution flows. It preserves local provider risk and related tests, keeps observed/inferred confidence separate, and expands only evidence-backed blast radius while preserving private-path redaction.

## Operating pipeline

1. Intake and provenance
2. Repository packing and scoped context
3. Semantic/code graph construction
4. Architecture visualization
5. Documentation and repository Q&A
6. License and security gate
7. Capability extraction
8. Evidence-backed clean-room rebuild specification
9. Verification and evidence packaging
10. Promotion decision by the parent steward

## Non-goals

- No blind vendoring.
- No direct production mutation from discovery.
- No commercial use of non-commercial dependencies as embedded core.
- No promotion when license provenance is unknown.
- No private repository metadata committed to this public repository.

## Current stack direction

- Repomix: primary repository packer/context formatter.
- Gitingest: lightweight ingest fallback and remote digest.
- Code2Prompt: scoped prompt/context generation and agent skill candidate.
- CodeGraph: preferred permissively licensed semantic graph candidate.
- GitDiagram: architecture visualization candidate.
- DeepWiki Open: repository wiki and Q&A candidate.
- Serena 1.7.0: pinned MIT semantic edit/refactor provider behind an isolated process boundary.
- Sazan rebuild-spec engine: primary evidence-backed clean-room reverse-engineering path.
- Sazan promotion gate: deterministic final evidence gate; never auto-promotes and always preserves parent steward authority.
- GitReverse: reference-only; current review found no detected license and its quick flow uses shallow repository evidence.
- GitNexus: benchmark/reference-only because the current license is non-commercial.
- ExplainGitHub: service/reference-only until an auditable open-source core and license are identified.

## Sub-agents

See `subagents/`.

Current specialized roles include intake, architecture graph, license/security, capability extraction, reverse engineering, and verification.

The parent Repo & Skill Steward remains the only promotion authority.
