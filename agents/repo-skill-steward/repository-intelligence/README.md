# Sazan Repository Intelligence Engine

Status: C001 ACTIVE
Date: 2026-09-30
Parent: Sazan Repo & Skill Steward

## Mission

Turn an external or internal repository into a structured evidence package that Sazan agents can understand, compare, test, and safely promote without blindly copying upstream code.

## Operating pipeline

1. Intake and provenance
2. Repository packing and scoped context
3. Semantic/code graph construction
4. Architecture visualization
5. Documentation and repository Q&A
6. License and security gate
7. Capability extraction
8. Reverse-engineering hypothesis
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
- Serena: optional external semantic edit/refactor adapter; do not vendor current GPL application code into the core.
- GitReverse: reference-only until licensing is verified.
- GitNexus: benchmark/reference-only because the current license is non-commercial.
- ExplainGitHub: service/reference-only until an auditable open-source core and license are identified.

## Sub-agents

See `subagents/`.

The parent Repo & Skill Steward remains the only promotion authority.
