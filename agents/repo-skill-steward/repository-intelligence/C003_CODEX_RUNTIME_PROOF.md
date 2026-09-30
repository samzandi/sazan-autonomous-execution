# C003 Codex Runtime Proof

Context: C003
Date: 2026-09-30
Status: BLOCKED
Milestone: 1

## Goal

Prove the promoted C002 Repository Intelligence pipeline through a live authorized Codex execution while preserving the same privacy, budget, provider, rollback, and parent-review invariants.

## Runtime pinning

- Codex GitHub Action: openai/codex-action pinned to commit 86365089eb2b84e0a8fb0717b304f8bdcb13b20e.
- Codex CLI: 0.159.2.
- Model: gpt-5.6-sol.
- Permission profile: read-only.
- Safety strategy: drop-sudo.
- Prompt is stored in a repository file rather than supplied inline.
- Output is constrained by a JSON schema and independently validated after the model run.

## Live proof

The workflow must:

1. verify that the OpenAI API key prerequisite exists without printing it;
2. run the deterministic C002 end-to-end baseline;
3. launch Codex against the checked-out repository in read-only mode;
4. require Codex to run focused C002 regression tests and the deterministic baseline;
5. require the workspace to remain unchanged;
6. require the final Repository Intelligence state to remain ready-for-parent-review;
7. require auto-promotion to remain disabled;
8. require private identity redaction;
9. validate the Codex result with a non-model Python validator.

## Promotion rule

This milestone must not be promoted merely because the workflow definition compiles.

Terminal states:

- VERIFIED: live Codex run passed and the independent validator accepted the evidence.
- BLOCKED: runtime credential, runtime execution, evidence, privacy, workspace-integrity, or promotion-boundary checks failed.

## Required external prerequisite

The GitHub repository must have an Actions secret named OPENAI_API_KEY. The secret value is never committed, logged, or persisted in the Repository Intelligence evidence package.

Status remains CANDIDATE until a live workflow run is VERIFIED.


## Live execution evidence

Workflow run: 36766115291

Attempt sequence:
- initial run: blocked before Codex because OPENAI_API_KEY was absent;
- rerun after configuring the secret: prerequisite, validator tooling, and deterministic C002 baseline all passed;
- Codex 0.159.2 started successfully with gpt-5.6-sol, read-only sandbox, approval=never, and drop-sudo hardening;
- provider reported: codex-action-responses-proxy;
- live request failed with: Quota exceeded. Check your plan and billing details.;
- a second rerun reproduced the same quota blocker.

Interpretation:
- repository wiring is valid;
- the secret is present and accepted by the action;
- Codex runtime installation and sandbox initialization are valid;
- no Repository Intelligence invariant failed;
- the external OpenAI API quota prevents model execution from completing.

Promotion remains forbidden while this blocker exists.
