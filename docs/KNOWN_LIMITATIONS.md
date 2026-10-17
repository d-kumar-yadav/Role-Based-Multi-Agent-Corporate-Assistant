# Meridian AccessPilot — Known Limitations & Production Roadmap

Meridian AccessPilot is built as an enterprise demonstration of role-based multi-agent RAG architecture. This document provides an honest assessment of current design trade-offs, operational boundaries, and areas requiring production hardening.

---

## 1. Performance & Latency

### Free-Tier Rate Limits vs. Architectural Cost
- **Measured Latency:** In evaluation benchmarks, latency is p50 26.4s and p95 46.4s.
- **Root Cause:** This latency is an artifact of Groq's free-tier rate limits (specifically the 8,000 Tokens Per Minute limit on `gpt-oss-20b`). When token usage approaches the window ceiling, the client experiences enforced backoff delays.
- **Paid-Tier Comparison:** On an enterprise tier without rate throttles, the architectural latency (hybrid retrieval + local guardrails + model inference) drops to **3–5 seconds p50**.

### Cross-Domain Overhead
- Cross-domain queries that fan out to multiple agents (e.g., HR and IT simultaneously) incur roughly double the latency of single-domain queries. Although agents execute in parallel, merging and synthesizing partial answers requires an additional LLM generation step.

---

## 2. Evaluation Methodology

### Citation Subset Matching
- The evaluation harness scores answer correctness by checking whether the expected document IDs form a subset of cited IDs (`expected_ids.issubset(cited_ids)`).
- **Limitation:** An answer that cites the correct document ID but produces an incomplete or poorly phrased summary is counted as correct.
- **Production Standard:** Stricter automated evaluators (such as Ragas or DeepEval) measuring answer faithfulness, context recall, and semantic similarity against human ground truth would provide more nuanced, albeit lower, scores.

---

## 3. Security & Guardrails

### Indirect Prompt Injection via Poisoned Documents
- While user prompts pass through 5 stages of input guardrails, documents ingested into the vector database could contain indirect prompt injections.
- The retrieval sanitizer filters known injection signatures, but an attacker with write access to internal corporate documents could embed sophisticated instructions that survive heuristic sanitization.

### NLI Non-Blocking Signal
- In accordance with the tiered groundedness design, the NLI model acts as an observability signal and does not gate the user's response.
- If an enterprise requires NLI to actively block responses, the underlying cross-encoder model must be domain-adapted or fine-tuned specifically on dense legal and corporate policy corpora.

---

## 4. Corpus & Data

### Synthetic Policy Documents
- The knowledge base contains 17 synthetic policy documents created for Meridian Global Technologies. No proprietary or actual corporate data is present.

### OCR & Table Extraction Artifacts
- The source PDF documents contained formatting and extraction artifacts resulting from automated parsing. Two documents (`public_02` and `public_05`) contained corrupted multi-column tables that required manual cleanup and text reconstruction during data migration.

---

## 5. Operational Constraints

### Response Cache Invalidation
- The response cache key is formed as `(query, user_role)`.
- It does not currently incorporate the user's explicit `department` list. If two employees share the same role (e.g., `manager`) but belong to different departments, a cross-department query could theoretically serve a cached response generated for the other department within the short cache TTL (10 minutes).

### State Persistence in Multi-Worker Environments
- Thread checkpointers and SQLite metric databases operate locally against filesystem paths.
- Running multiple Uvicorn worker processes (`--workers > 1`) or multi-pod Kubernetes deployments will lead to SQLite write locks and non-shared conversation memory across workers.

### Lack of API Rate Limiting
- The `/query` endpoint currently lacks token-bucket or sliding-window rate limiting per IP or user token. High-concurrency traffic can exhaust upstream LLM rate quotas.

---

## 6. Production Roadmap

For enterprise-grade production readiness, the following enhancements are prioritized:

1. **Self-Hosted Inference Engine:** Deploy an internal vLLM cluster hosting `Llama-3.1-8B-Instruct` or `Qwen2.5-7B` with dedicated GPU acceleration, eliminating external API rate limits, per-minute quotas, and external data transit.
2. **Postgres Checkpointer & Distributed Storage:** Replace local SQLite and MemorySaver with `PostgresSaver` for thread state persistence and persistent hash-chained audit storage, supporting horizontal scaling across multiple workers.
3. **Prometheus & Grafana Observability:** Connect enterprise monitoring to the `/metrics` endpoint to visualize latency distributions, cache hit ratios, and guardrail block counts in real-time dashboards.

