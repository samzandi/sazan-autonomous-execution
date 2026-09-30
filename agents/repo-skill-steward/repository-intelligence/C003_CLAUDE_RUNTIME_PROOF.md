# C003 Claude Code Runtime Proof

Context: C003
Date: 2026-09-30
Status: CANDIDATE
Milestone: 2

## Goal

Prove the promoted C002 Repository Intelligence pipeline through a live authorized Claude Code execution while preserving the same privacy, budget, provider, rollback, and parent-review invariants.

## Runtime pinning

- Claude Code GitHub Action: anthropics/claude-code-action pinned to commit 12dd8d74c712f5f3669365b2369b558c495b1104.
- Pinned action revision bundles Claude Code 2.1.286.
- Model: claude-opus-5.
- Permission mode: auto.
- Repository token permissions: read-only.
- Explicit tool allow-list limits shell execution to verification commands.
- Structured output is constrained by JSON Schema and independently validated.

## Supported authentication

The workflow accepts either:

- ANTHROPIC_API_KEY; or
- CLAUDE_CODE_OAUTH_TOKEN.

Secret values are never committed, printed, or persisted in Repository Intelligence evidence.

## Promotion rule

VERIFIED requires:
- deterministic C002 baseline passes;
- live Claude Code execution completes;
- focused tests pass;
- repository HEAD matches;
- workspace remains unchanged;
- parent-review boundary is observed;
- auto-promotion remains disabled;
- private identity redaction remains intact;
- independent non-model validation passes.

Otherwise the milestone remains BLOCKED and may not be promoted.
