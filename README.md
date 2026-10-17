# Meridian AccessPilot — Enterprise RBAC-Aware Multi-Agent Copilot

An enterprise AI assistant that answers employee HR, IT, and Finance
questions while enforcing role-based access control, blocking unsafe
queries, and producing cited, grounded answers.

Built as a demonstration of production-grade RAG design: layered safety
gates, tiered groundedness verification, multi-agent fan-out for
cross-functional queries, and a full audit trail.

## Problem

Enterprise employees waste hours searching for policy answers across
scattered document systems, raising IT/HR tickets for questions already
answered in a policy document, and waiting on approvals that could be
routed automatically. Meanwhile, naive AI assistants introduce two new
risks: data leakage across access boundaries, and confident hallucinations
of policy details that don't exist.

This project addresses both: a copilot that answers employee questions
from internal policy documents with strict access control, cited sources,
and measured safety behavior.

## Evaluation Results

Measured on a 60-query evaluation set (30 golden, 20 red team,
10 unauthorized).

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
| Performance | p50 latency | 26.4s (free-tier) |
| | p95 latency | 46.4s (free-tier) |

**Note on latency:** On a paid inference tier, latency drops to 3-5s
p50. The free-tier latency reflects per-minute token limits, not
architectural cost. See `docs/KNOWN_LIMITATIONS.md`.

## Architecture

    User Request (JWT-authenticated)
      |
    [Input Guardrails — 5 stages]
      Regex jailbreak filter
      PII detection (Presidio)
      Dialog classifier (MiniLM embeddings)
      Off-topic embedding check
      LLM firewall (gpt-oss-20b)
      |
    [Query Expansion] (cached, gpt-oss-120b)
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

## LLM Usage

LLMs are used only where reasoning is required. Every other component
is deterministic code.

| Query type | LLM calls | Where |
|---|---|---|
| Dialog ("hello") | 0 | Canned responses |
| Single-domain | 2 | Input firewall + domain agent |
| Cross-domain | 3-4 | Firewall + 2 agents + synthesizer |
| Cache hit | 0 | LRU response cache |

See `docs/ARCHITECTURE.md` for the complete LLM usage map.

## Model Selection

| Component | Model | Purpose |
|---|---|---|
| Dialog routing | all-MiniLM-L6-v2 | Fast 5-class intent classification |
| Document retrieval | BAAI/bge-small-en-v1.5 | 384-dim dense embeddings |
| Sparse retrieval | Qdrant/BM25 | Keyword matching for exact terms |
| Reranking | BAAI/bge-reranker-base | Cross-encoder precision rerank |
| Groundedness signal | cross-encoder/nli-deberta-v3-base | NLI entailment scoring |
| PII detection | en_core_web_md (spaCy) | Named entity recognition |
| Input firewall | gpt-oss-20b (Groq) | Fast safety classification |
| Agent reasoning | gpt-oss-20b (Groq) | Answer generation |

Chosen for a balance of accuracy, latency, and free-tier cost. All
local models run on CPU without GPU.

## Groundedness Design

The groundedness pipeline is two-tiered:

- **Tier 1 (blocks):** citation verification, majority anchor failure,
  input regex, PII detection, RBAC filters. Deterministic. No false
  positives in practice.
- **Tier 2 (informs):** NLI entailment scoring, partial anchor mismatch.
  ML-based. Logged to audit trail, never gates a response.

This design eliminates the false-positive problem that binary
groundedness blocking created. See `docs/GROUNDEDNESS_DESIGN.md`
for the full design rationale.

## Quick Start (Local)

Requirements:
- Python 3.11+
- Groq API key (free tier works)

    # 1. Set up virtual environment
    python -m venv venv
    venv\Scripts\activate

    # 2. Install dependencies
    pip install -r requirements.txt

    # 3. Configure environment
    cp .env.example .env
    # Edit .env and set GROQ_API_KEY and FIREWALL_GROQ_API_KEY

    # 4. Ingest policy documents into Qdrant
    python -m app.rag.ingest --reset

    # 5. Start the backend (Terminal 1)
    uvicorn app.main:app --host 0.0.0.0 --port 8000

    # 6. Start the frontend (Terminal 2)
    streamlit run dashboard/streamlit_app.py --server.port 8501

Backend runs at http://localhost:8000
Frontend runs at http://localhost:8501

## Security Model

- **Authentication:** JWT with per-user role and department claims
- **Authorization:** Qdrant native filter applied before retrieval
- **Input safety:** 5-stage pipeline from regex to LLM classifier
- **Output safety:** Tiered groundedness, PII redaction
- **Audit:** Hash-chained, tamper-evident log with PII redaction
- **Thread isolation:** Thread IDs namespaced per user

## Documentation

- `docs/ARCHITECTURE.md` — system design and LLM usage map
- `docs/EVALUATION.md` — eval methodology and results
- `docs/GROUNDEDNESS_DESIGN.md` — groundedness design decision
- `docs/KNOWN_LIMITATIONS.md` — honest limitations and future work
- `docs/PHASE_11_SUMMARY.md` — Phase 11 stabilization report

## Known Limitations

This is a demonstration system, not a production deployment. See
`docs/KNOWN_LIMITATIONS.md` for the full list. Key items:

- Latency reflects Groq free-tier rate limits
- Answer correctness uses citation subset matching, not semantic
  similarity
- Response cache is per (query, role), not per (query, role,
  department)
- Cross-domain latency is roughly 2x single-domain

## License

Not licensed for production use. Educational and portfolio purposes only.

