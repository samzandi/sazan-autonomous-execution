# C002 Incremental State and Cache Strategy

Context: C002
Date: 2026-09-30
Status: LAB VALIDATION

## Purpose

Avoid unnecessary Repository Intelligence recomputation while preserving evidence integrity, privacy, provider contracts, policy gates, and deterministic invalidation.

## Core rule

A repository revision alone is not a safe or useful cache key.

Revision is retained as provenance. Cross-revision reuse is permitted only when the exact stage input fingerprint and all other compatibility dimensions remain unchanged.

## Cache descriptor

Every cacheable stage declares:

- privacy-safe repository ID;
- source revision;
- stage ID;
- selected provider;
- provider version;
- provider capability contract;
- stage input fingerprint;
- policy fingerprint;
- implementation fingerprint;
- dependency fingerprints;
- reuse policy.

Private repository source names are never required.

## Semantic cache identity

The reusable cache identity includes:

- repository ID;
- stage;
- provider and provider version;
- provider contract;
- stage input fingerprint;
- policy fingerprint;
- implementation fingerprint;
- dependency fingerprints.

Revision is intentionally excluded from the default semantic identity. This allows safe reuse across commits only when the stage's real inputs remain byte/fingerprint equivalent.

## Reuse policies

Baseline policies:

- `same-revision-only`;
- `fingerprint-stable-cross-revision`.

Production default for deterministic analysis stages is `fingerprint-stable-cross-revision`.

A stage that mutates source state, depends on volatile external state, or cannot produce a complete input fingerprint must use `same-revision-only` or disable caching.

## Invalidation

A cache miss is mandatory when any of the following changes:

- repository ID;
- stage;
- provider;
- provider version;
- provider capability contract;
- stage input fingerprint;
- policy fingerprint;
- implementation fingerprint;
- any dependency fingerprint;
- revision under a same-revision-only policy;
- cache-key integrity;
- result fingerprint availability.

Provider health is evaluated before cache acceptance. A cache entry does not make an unhealthy or ineligible provider eligible.

Budget policy is represented in the policy fingerprint. A cache hit therefore cannot silently bypass changed budget policy.

## Dependency chaining

Downstream stages include fingerprints for the upstream artifacts/receipts they actually consume.

Examples:

- semantic graph depends on source/context fingerprint;
- architecture presentation depends on graph fingerprint;
- Wiki/Q&A depends on graph/context fingerprints;
- reverse engineering depends on verified evidence-package fingerprints.

A changed upstream dependency automatically invalidates downstream cache entries.

## Artifact integrity

Cache entries persist result and artifact fingerprints, not unverified filenames alone.

Restored artifacts must be fingerprint-verified before reuse.

## Cache hit semantics

A cache hit means only that an equivalent stage result may be reused.

It does not:

- bypass current license/security policy;
- bypass provider health routing;
- bypass budget policy;
- bypass verifier requirements;
- auto-promote;
- convert inferred evidence into observed evidence.

## Privacy

Persistent cache indexes use privacy-safe repository IDs only.

Private/internal source paths or names must not appear in shared/public cache metadata.

## Storage boundary

The baseline engine defines deterministic receipts and invalidation semantics. Physical cache storage may be local filesystem, CI cache, object storage, or another backend behind the same receipt contract.

Backend selection is not part of the cache identity.

## Promotion boundary

Cached evidence is still evidence subject to the same parent Repo & Skill Steward promotion gate.
