# Meridian AccessPilot — Enterprise RBAC-Aware Multi-Agent Copilot

An enterprise AI assistant that answers employee HR, IT, and Finance questions while enforcing strict role-based access control, blocking unsafe queries, and producing cited, grounded answers.

Built as a demonstration of production-grade RAG design: layered safety gates, tiered groundedness verification, multi-agent fan-out for cross-functional queries, and a full audit trail.

## Problem

Enterprise employees waste hours searching for policy answers across scattered document systems, raising IT/HR tickets for questions already answered in a policy document, and waiting on approvals that could be routed automatically. 

Meanwhile, naive AI assistants introduce two new risks: **data leakage across access boundaries**, and **confident hallucinations** of policy details that don't exist. This project addresses both: a copilot that answers employee questions from internal policy documents with strict access control, cited sources, and measured safety behavior.

## Features

- **Chunk-Level RBAC**: Employees only retrieve documents their role is authorized to see (enforced natively in Qdrant).
- **Multi-Agent Fan-Out**: Cross-functional queries (e.g., "WFH monitor reimbursement") are routed to IT and Finance agents in parallel, then synthesized.
- **Tiered Groundedness**: Deterministic checks block hallucinations, while ML signals (NLI) log to the audit trail without blocking valid answers.
- **5-Stage Input Firewall**: Regex, Presidio (PII), MiniLM (dialog), embedding similarity, and a Role-Aware LLM classifier.
- **Persistent Chat History**: SQLite-backed frontend with multi-thread support and user profile management.
- **Observability**: Hash-chained audit logs, Prometheus metrics, and a restricted HR/Executive dashboard.
- **Zero External Vector DB Dependencies**: Can run fully locally with embedded Qdrant.

## Evaluation Results

Measured on a 60-query evaluation set (30 golden, 20 red team, 10 unauthorized).

| Category | Metric | Value |
|---|---|---|
| Golden QA (30) | Retrieval precision | **93.3%** (28/30) |
| | Answer correctness | **93.3%** (28/30) |
| Red Team (20) | Overall block rate | **100%** (20/20) |
| | Jailbreak | 100% (5/5) |
| | Off-topic | 100% (5/5) |
| | Sensitive-topic | 100% (5/5) |
| | Social engineering | 100% (5/5) |
| Unauthorized (10) | Refusal rate | **100%** (10/10) |

**Note on latency:** p50 latency is currently ~26s on the Groq free tier due to strict per-minute token limits. On a paid inference tier, latency drops to 3-5s p50. See `docs/KNOWN_LIMITATIONS.md`.

## Engineering Highlights (Hard Bugs Solved)

Building a RAG pipeline is easy; making it secure and reliable is hard. Here are the critical edge cases discovered and fixed during development:

1. **The Stale Cache Data Leak**: After updating the RBAC rules to separate Finance-only memos from general policies, an employee test account still received restricted revenue figures. Root cause: A stale cache hit. The system served the answer generated *before* the security rule was applied. Fix: Implemented a cache invalidation strategy and moved the RBAC filter upstream.
2. **Mixed-Content RBAC Failure**: A Finance policy file contained both general expense rules (for everyone) and executive memos (for Finance only). Tagging the whole file as `internal` caused a leak. Fix: Split the corpus into `FIN-POLICY-001.md` (internal) and `FIN-MEMOS-001.md` (finance_only).
3. **Groundedness False Positives**: The NLI groundedness model was blocking valid answers because it misclassified corporate policy language. Fix: Redesigned into a two-tier system where deterministic regex blocks hard failures, while ML signals only inform the audit log.
4. **Unicode Regex Failures**: The LLM consistently generated fullwidth brackets (`【 】`) and non-breaking spaces (`\u202f`), which broke exact-match citation regex. Fix: Built a Unicode canonicalization layer before every verification step.

## Architecture

```text
User Request (JWT-authenticated)
  |
[Input Guardrails — 5 stages]
  Regex jailbreak filter
  PII detection (Presidio)
  Dialog classifier (MiniLM embeddings)
  Off-topic embedding check
  Role-aware LLM firewall (gpt-oss-20b)
  |
[Query Expansion] (cached)
  |
[Router] — keyword domain classification (no LLM)
  |
[Retriever]
  Hybrid search: BGE-small dense + BM25 sparse
  Qdrant RBAC filter (access_level + roles)
  Cross-encoder reranker (bge-reranker-base)
  |
[Fan-out] — parallel agents per domain
  HR Agent | IT Agent | Finance Agent
  |
[Synthesizer] — merge multi-domain answers
  |
[Output Guardrails]
  Toxicity keyword check
  Tiered groundedness verification
  PII redaction (fails open)
  |
[Response with citations]
  |
[Audit Log — hash-chained] + [Metrics DB — SQLite]
