# C003 Reproducibility Pack

Context: C003
Date: 2026-09-30
Status: CANDIDATE
Milestone: 5

## Goal

Produce a deterministic, machine-verifiable evidence pack that can reconstruct the exact Repository Intelligence implementation and its verified evidence for a specific repository revision.

## Pack contents

The generated pack records:

- exact repository revision and Git tree hash;
- clean-workspace state;
- SHA-256 and byte size of required Repository Intelligence source, policy, and workflow files;
- immutable/version-pinned external tools;
- artifact checksums where the verified workflow already enforces them;
- verified workflow run IDs for the promoted C002/C003 local milestones;
- explicit blocked status for live Codex and Claude runtime proofs;
- deterministic reproduction commands;
- a canonical pack fingerprint.

## Determinism

The pack contains no timestamp or machine-specific absolute path.

For the same Git revision and specification:
- two generated packs must be byte-for-byte equivalent after canonical JSON serialization;
- the validator rebuilds the expected pack from the repository and rejects any revision, tree, file, tool, evidence, command, or fingerprint drift.

## Truthful blocked evidence

The pack records blocked live-runtime proofs rather than converting them into success:
- Codex remains blocked by external API quota;
- Claude Code remains blocked by external runtime authentication.

This means reproducibility can be verified independently while release readiness remains correctly blocked.

Status remains CANDIDATE until the reproducibility lab and repository regressions pass.
