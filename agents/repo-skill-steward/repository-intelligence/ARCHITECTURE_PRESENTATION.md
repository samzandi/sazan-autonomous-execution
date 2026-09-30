# Architecture Presentation Policy

Context: C001
Date: 2026-09-30
Status: LAB VALIDATION

## Decision

The default Sazan architecture presentation path is an internal deterministic Mermaid renderer fed by semantic graph evidence.

## Why GitDiagram is not a core dependency

GitDiagram is MIT licensed and has a strong presentation pipeline, but its full self-hosted application currently depends on:
- Bun and a Next.js runtime;
- Cloudflare R2;
- Upstash Redis;
- an OpenAI or OpenRouter API key for diagram generation;
- additional provider and rendering dependencies for explainer videos.

That stack is useful as a standalone product, but excessive for Sazan's baseline repository-analysis pipeline.

GitDiagram remains valuable as:
- an optional external visualization for public repositories;
- a UX/reference implementation for interactive architecture exploration;
- a reference for deterministic graph-to-Mermaid compilation, validation, sanitization, and export behavior.

## Privacy rule

Do not send private repository structure or code to the hosted GitDiagram service by default.
Private-repository use requires an explicit authorization path and separate credential handling.

## Sazan renderer

Input:
- CodeGraph-style JSON nodes and edges.

Output:
- bounded Mermaid flowchart source suitable for Markdown and GitHub rendering.

Properties:
- deterministic output;
- Python standard library only;
- no network access;
- no API keys;
- excludes external nodes by default;
- configurable node and edge limits;
- sanitized labels;
- stable opaque node identifiers derived from source IDs;
- provider-independent input contract.

## Presentation routing

1. Use the internal Sazan Mermaid renderer for repository documentation, CI artifacts, and private repositories.
2. Use CodeGraph-generated architecture prose for evidence-backed textual summaries.
3. Use GitDiagram only as an optional external visualization/reference when its richer interactive UI materially helps and repository privacy allows it.
4. Do not make GitDiagram availability a prerequisite for Repository Intelligence.

## Future presentation adapters

The same normalized graph contract may later feed:
- SVG/PNG renderers;
- interactive web graph views;
- Figma diagrams;
- repository README architecture snapshots;
- multi-repository maps.
