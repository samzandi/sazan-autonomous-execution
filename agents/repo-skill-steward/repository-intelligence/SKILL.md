# Sazan Repository Intelligence

## Purpose

Provide evidence-driven repository understanding for the parent Sazan Repo & Skill Steward.

## Trigger

Use when a repository must be evaluated, reverse engineered, compared, documented, or prepared for safe capability extraction.

## Required stages

1. Intake
   - Record canonical repository, revision, source, visibility class, and requested purpose.
   - Never persist private repository names in this public repository.

2. Context build
   - Prefer Repomix for full/filtered context packing.
   - Use Gitingest for lightweight remote digest.
   - Use Code2Prompt when a scoped, templated, agent-oriented prompt is more efficient.

3. Structure and semantics
   - Build a semantic dependency view with a permissively licensed graph engine.
   - Current preferred candidate: CodeGraph (Apache-2.0).
   - Do not treat text packing as a substitute for dependency/call analysis.

4. Documentation and visualization
   - Generate architecture views with GitDiagram where useful.
   - Use DeepWiki Open or an equivalent self-hosted layer for wiki/Q&A.

5. License and security gate
   - Verify license from the canonical source before integration.
   - Detect install scripts, secrets access, network calls, binary downloads, privileged operations, workflow mutations, and unsafe shell execution.
   - Unknown license means reference-only.
   - Non-commercial license means no embedded use in Sazan commercial core.

6. Capability extraction
   - Extract concepts, interfaces, algorithms, tests, UX patterns, and architectural techniques.
   - Prefer reimplementation from documented behavior when copying code would create licensing or coupling risk.

7. Verification
   - Require source citations/evidence, reproducible checks, and a rollback path.
   - Compare claims against repository code or canonical documentation.

8. Output
   - Produce an evidence package with: purpose, architecture, dependencies, license, security notes, strengths, limitations, reusable capabilities, rejected items, and recommended next action.

## Promotion rule

Repository Intelligence may propose; the parent Repo & Skill Steward decides promotion.
No evidence = no promotion.
