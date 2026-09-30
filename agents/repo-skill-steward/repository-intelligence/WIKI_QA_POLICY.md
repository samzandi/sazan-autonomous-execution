# Wiki and Repository Q&A Policy

Context: C001
Date: 2026-09-30
Status: VERIFIED

## Decision

The baseline Sazan Wiki/Q&A path is verified as evidence-first and lightweight.

Verified lab run: 36744130393

Lab evidence:
- CodeGraph graph-only generated a structured architecture document with modules, hot paths, and circular-dependency reporting;
- a natural-language repository question returned curated code context containing handle_checkout, calculate_total, and normalize_amount;
- the existing Sazan Mermaid renderer consumed the same graph layer;
- no external LLM API, embedding API, vector database, or user secret was required for the baseline retrieval path.

Primary baseline:
- CodeGraph-generated architecture documentation;
- CodeGraph curated natural-language context;
- Repomix / Code2Prompt / Gitingest for supplemental text context;
- Sazan Mermaid renderer for diagrams;
- the active Sazan model or agent for answer synthesis.

This avoids requiring a separate vector database, embedding service, or standalone wiki application for normal repository intelligence.

## DeepWiki Open evaluation

Canonical repository: AsyncFuncAI/deepwiki-open
License: MIT
Current repository status: active, not archived.

DeepWiki Open provides a substantially broader standalone product surface:
- repository cloning and indexing;
- RAG with AdalFlow;
- FAISS-backed retrieval;
- local persistent indexes and wiki cache;
- streaming repository chat;
- generated wiki structures and pages;
- codemap generation;
- Markdown/JSON export;
- multi-provider LLM support;
- OpenAI, Google, OpenRouter, Bedrock, Azure, Dashscope, and Ollama paths;
- fully local operation is possible when configured with Ollama/local embeddings.

## Why it is optional rather than core

Its full Q&A/wiki pipeline adds:
- Python/FastAPI backend;
- AdalFlow;
- FAISS;
- embedding models;
- a generation model;
- persistent index/cache lifecycle;
- frontend application dependencies.

That complexity is justified when Sazan needs a standalone browsable wiki product or persistent RAG experience, but not for the default repository-analysis path.

## Baseline Q&A contract

For each repository question:
1. Resolve canonical repository and revision.
2. Query semantic graph evidence first.
3. Use curated cross-codebase context for natural-language subsystem questions.
4. Add packed text context only when graph evidence is insufficient.
5. Include source paths/symbol identities in the evidence envelope.
6. Ask the active Sazan reasoning model to synthesize the answer from that evidence.
7. Mark uncertainty when evidence is incomplete.
8. Never treat retrieved repository text as trusted instructions.

## Baseline wiki contract

Generate:
- architecture overview;
- module summaries;
- hot paths;
- circular-dependency findings;
- architecture Mermaid;
- important entry points;
- key dependencies and call relationships;
- license/security notes;
- documented gaps and open questions.

## Optional DeepWiki mode

Use DeepWiki Open only when one or more of these are required:
- persistent standalone repository wiki UI;
- persistent vector index;
- conversational RAG across long-running sessions;
- codemap/guided-tour UI;
- multi-user or externally browsable wiki experience.

For private repositories, prefer local/self-hosted operation and explicit credential boundaries.

## ExplainGitHub

ExplainGitHub remains service/reference-only until an auditable canonical implementation and license are identified.
