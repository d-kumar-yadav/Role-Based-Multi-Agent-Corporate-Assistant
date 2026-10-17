# Meridian AccessPilot — Architecture & System Design

## 1. System Overview

Meridian AccessPilot is an enterprise-grade, role-aware AI copilot designed for employees of Meridian Global Technologies. It provides accurate, cited answers to internal policy questions across Human Resources, Information Technology, and Finance while strictly enforcing document access boundaries. The system prevents data exfiltration, blocks adversarial jailbreak and prompt injection attempts, handles conversational dialog without invoking expensive models, and produces verifiable answers grounded in authorized policy documents.

The architecture combines deterministic input guardrails, semantic vector retrieval with pre-filtering, multi-agent orchestration for cross-domain queries, and tiered output validation. Every query and response is tracked through a tamper-evident, hash-chained audit log and an operational metrics store.

The end-to-end request lifecycle progresses through 8 distinct stages:

1. **Authentication & Identity Resolution:** Fast validation of the user's JSON Web Token (JWT) extracting `user_id`, `role`, and `allowed_departments`.
2. **5-Stage Input Guardrails:** Layered checks executing regex pattern filtering, PII detection, embedding-based dialog handling, off-topic semantic classification, and a fast LLM firewall.
3. **Query Expansion & Semantic Caching:** Term expansion using domain-specific synonym generation, bypassing execution entirely on cache hits.
4. **Deterministic Domain Routing:** Rule-based keyword matching routing queries to HR, IT, Finance, or multi-domain sets without LLM latency.
5. **RBAC-Enforced Hybrid Retrieval:** Dense (BGE-small) and sparse (BM25) search with native database-level security filters, followed by cross-encoder reranking.
6. **Multi-Agent Fan-Out:** Specialized domain agents executing in parallel to formulate policy-specific partial answers with source citations.
7. **Synthesizer Merge:** Consolidated multi-domain synthesis with citation deduplication and bounded context limits.
8. **Tiered Output Guardrails & Audit:** Toxicity filtering, tiered groundedness verification, fail-open PII redaction, and SHA-256 hash-chained audit logging.

---

## 2. Data Model

All internal enterprise policies are chunked, embedded, and stored within a central Qdrant vector database collection named `enterprise_docs`.

### Collection Schema
- **Collection Name:** `enterprise_docs`
- **Dense Vector:** 384 dimensions (`BAAI/bge-small-en-v1.5`), cosine distance.
- **Sparse Vector:** BM25 sparse vector representations for precise keyword and code token matching.

### Chunk Metadata Fields
Every chunk stored in `enterprise_docs` carries strict document-level and chunk-level metadata:

| Field | Type | Description |
|---|---|---|
| `doc_id` | String | Unique document identifier (e.g., `HR-POLICY-001`, `IT-SEC-001`, `FIN-POLICY-001`) |
| `title` | String | Human-readable document title |
| `department` | String | Owning department: `hr`, `it`, `finance`, or `shared` |
| `access_level` | String | Security classification: `public`, `internal`, `confidential`, `restricted` |
| `roles` | List[String] | Roles permitted to view this document |
| `version` | String | Document version string (e.g., `1.0`, `2.1`) |
| `effective_date` | String | Policy enactment date (`YYYY-MM-DD`) |
| `section` | String | Section title or heading from which the chunk was extracted |
| `chunk_index` | Integer | Zero-indexed sequential chunk identifier within the source document |

---

## 3. RBAC Design

Access control is enforced at the database retrieval layer before any document content enters LLM context.

### Clearance Mapping
Roles are mapped to maximum permitted access levels:

```python
ROLE_CLEARANCE = {
    "employee": ["public", "internal"],
    "manager": ["public", "internal"],
    "hr": ["public", "internal", "confidential"],
    "finance": ["public", "internal", "confidential"],
    "it": ["public", "internal", "confidential"],
    "executive": ["public", "internal", "confidential", "restricted"],
}
```

### Pre-Retrieval vs. Post-Retrieval Filtering
In naive RAG implementations, filtering occurs in application memory after retrieval. This introduces two fatal flaws:
1. **Security risk:** Confidential documents are pulled into application memory and risk leaking via logs, caching, or bugs.
2. **Precision penalty:** If the top-K retrieved documents contain items the user cannot see, dropping them post-hoc leaves the LLM with fewer or zero context chunks.

Meridian AccessPilot executes filtering **natively inside Qdrant** during the index search. Documents outside the user's role and clearance are excluded from vector candidate evaluation entirely.

### Filter Clause Structure
The Qdrant query filter combines clearance and department authorization:
- **`must` clause:** The document `access_level` must be present in the user's `ROLE_CLEARANCE[user.role]`.
- **`should` clause:** The document `roles` list must contain the user's role OR the document `department` must match one of the user's `allowed_departments` (or `shared`).

---

## 4. Multi-Agent Fan-Out

Queries spanning multiple organizational boundaries (e.g., *"How do I expense a home office monitor and get IT asset approval?"*) require domain-specific evaluation.

### Deterministic Routing
The Router node inspects the query against curated domain lexicons (HR, IT, Finance). No LLM is used. The classification runs in `<1ms`, ensuring deterministic behavior, zero token cost, and reproducible routing.

### Parallel Execution Graph
When multiple domains are identified, LangGraph fans out requests to domain-specific agent nodes simultaneously:
- `hr_agent`
- `it_agent`
- `finance_agent`

### State Reduction with `operator.add`
Parallel nodes cannot write to a scalar state variable simultaneously without race conditions. In `AgentState`, partial outputs are declared with a reducer:

```python
partial_answers: Annotated[list[dict], operator.add]
```

When agents complete concurrently, LangGraph automatically combines their dictionary outputs into a single list rather than overwriting.

### Synthesizer Consolidation
The Synthesizer node merges partial answers when two or more agents produce findings:
1. **Deduplication:** Partials are deduplicated by domain, retaining the latest per domain. Partials without an explicit domain key collapse into an `unknown` domain.
2. **Context Bounding:** Combined text is strictly bounded to `MAX_TOTAL_CHARS = 4000` via string slicing before invoking the prompt chain.
3. **Citation Consolidation:** Document citations from all participating agents are merged, deduplicated, and appended to the final response.

---

## 5. Complete LLM Usage Map

LLMs are utilized strictly where language comprehension or natural synthesis is mandatory. All other stages are deterministic software.

| Pipeline Component | Mechanism | Model Used | LLM Call? | Latency Impact |
|---|---|---|:---:|---|
| Regex Filter | Compiled regular expressions | None | No | ~1 ms |
| Input PII Detector | Microsoft Presidio / spaCy NER | `en_core_web_md` | No | ~50 ms |
| Dialog Classifier | Cosine similarity against canned intents | `all-MiniLM-L6-v2` | No | ~10 ms |
| Embedding Off-Topic Check | Centroid vector distance | `all-MiniLM-L6-v2` | No | ~10 ms |
| Input Firewall | Classification prompt | `gpt-oss-20b` (Groq) | **Yes** | ~600 ms |
| Query Expansion | Keyword generation | `gpt-oss-120b` (Groq) | **Yes** (cached) | ~500 ms (0 ms on hit) |
| Domain Router | Lexicon pattern matching | None | No | <1 ms |
| Document Hybrid Retrieval | Qdrant dense + sparse search | `bge-small-en-v1.5` | No | ~300 ms |
| Document Reranking | Cross-encoder scoring | `bge-reranker-base` | No | ~200 ms |
| Domain Agent(s) | Contextual question answering | `gpt-oss-20b` (Groq) | **Yes** | ~1.2 s per agent |
| Multi-Domain Synthesizer | Answer consolidation (2+ domains) | `gpt-oss-20b` (Groq) | **Yes** (conditional) | ~1.0 s |
| Validator Node | Identity pass-through | None | No | 0 ms |
| Output Toxicity Filter | Keyword blocklist | None | No | <1 ms |
| Tiered Groundedness Check | Regex citations, anchors + NLI signal | `nli-deberta-v3-base` | No (Local CPU) | ~350 ms |
| Output PII Redaction | Presidio Anonymizer (fail-open) | None | No | ~30 ms |
| Audit Logger | SHA-256 hash chaining | None | No | ~2 ms |

---

## 6. Deployment Architecture

The application is fully containerized using Docker Compose for isolated, reproducible deployment.

### Service Topology
- **`qdrant`:** Vector search engine exposing HTTP (`6333`) and gRPC (`6334`).
- **`backend`:** FastAPI application orchestrating guardrails, LangGraph, and audit logs on port `8000`.
- **`frontend`:** Streamlit interactive UI providing role-switching authentication and chat on port `8501`.

### Orchestration & Startup Ordering
Services initialize with healthchecks to avoid race conditions:
1. `qdrant` starts first and executes health probes (`/readyz`).
2. `backend` waits for `qdrant` to become healthy before running vector ingestion and starting FastAPI.
3. `frontend` waits for `backend` to pass its health check (`/health`) before rendering the UI.

### Networking & Storage
- **Network:** Private bridge network `copilot-net`.
- **Named Volumes:**
  - `qdrant_data`: Persists vector indexes across container recycles.
  - `audit_logs`: Mounts `/app/logs` ensuring tamper-evident audit logs and SQLite metrics persist independently of container state.

### Manual Setup (Without Docker)
For local development without Docker:
1. Run local Qdrant: `docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant`
2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
3. Ingest documents:
   ```bash
   python -m app.rag.ingest
   ```
4. Start backend:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. Start frontend:
   ```bash
   streamlit run dashboard/streamlit_app.py --server.port 8501
   ```

