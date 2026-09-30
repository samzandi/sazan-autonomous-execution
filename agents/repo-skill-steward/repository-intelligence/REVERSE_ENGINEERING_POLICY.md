# Reverse Engineering Policy

Context: C001
Date: 2026-09-30
Status: LAB VALIDATION

## Objective

Produce evidence-backed clean-room rebuild specifications from repositories without depending on a synthetic "original prompt" as the source of truth.

## GitReverse evaluation

Canonical repository: filiksyos/gitreverse

Current observed behavior:
- accepts a public GitHub repository;
- collects repository metadata;
- collects a full GitHub tree but intentionally formats only depth 1 for the quick reverse flow;
- reads the README and truncates it to 8,000 characters;
- sends metadata + depth-1 tree + README to an LLM;
- asks for one short conversational synthetic user message, approximately 120–200 words;
- supports several hosted LLM providers;
- optional Supabase caching/library and embeddings are separate product features.

License status in the current review:
- no root LICENSE file was found;
- GitHub repository metadata reports no detected license.

Policy consequence:
- GitReverse is reference-only;
- do not vendor or copy its implementation into the Sazan commercial core;
- the general concept of reconstructing an implementation request from repository evidence may be independently implemented.

## Sazan reverse-engineering model

GitReverse answers:
"What short prompt might have produced something like this repository?"

Sazan must answer:
"What evidence-backed specification would let an independent team reproduce the observable behavior, architecture contracts, operational constraints, and acceptance criteria without copying the original implementation?"

## Evidence hierarchy

Prefer evidence in this order when available:
1. executable tests and runtime behavior;
2. semantic graph relationships and symbol evidence;
3. configuration/build manifests and schemas;
4. source-level interfaces and contracts;
5. maintained project documentation;
6. README/product descriptions;
7. metadata and shallow file trees.

Lower-ranked evidence must not override contradictory higher-ranked evidence.

## Claim states

Every material claim has one state:
- observed;
- inferred;
- unknown.

Observed claims require one or more evidence IDs.
Inferred claims require supporting evidence IDs and an explicit rationale.
Unknown claims are preserved as questions or validation tasks.

## Clean-room boundary

The rebuild specification may describe:
- behavior;
- interfaces;
- protocols;
- data shapes;
- architectural relationships;
- algorithms at a behavior/requirements level;
- tests and acceptance criteria;
- operational constraints.

It must not intentionally reproduce:
- copyrighted source code;
- long source passages;
- proprietary text;
- unlicensed implementation details beyond what is necessary to describe observed behavior.

## Output artifacts

Baseline outputs:
- REBUILD_SPEC.md
- rebuild-spec.json
- evidence-ledger.json

Optional outputs:
- architecture Mermaid;
- acceptance-test plan;
- migration/adoption plan;
- feature-parity matrix.

## Promotion gate

A reverse-engineering output may be promoted only when:
- provenance is recorded;
- evidence references are valid;
- observed/inferred/unknown states are preserved;
- required sections are present;
- acceptance criteria exist;
- license/security constraints are attached;
- verifier returns verified or verified-with-constraints.
