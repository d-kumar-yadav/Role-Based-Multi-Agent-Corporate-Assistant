import logging
from qdrant_client.http import models
from qdrant_client.http.models import FieldCondition, MatchAny
from app.rag.vectorstore import get_vectorstore
from app.rag.reranker import rerank
from app.rag.query_expander import expand_query

logger = logging.getLogger("rag.retriever")

ROLE_CLEARANCE = {
    "employee":  ["public", "internal"],
    "manager":   ["public", "internal", "confidential"],
    "hr":        ["public", "internal", "confidential", "hr_only"],
    "finance":   ["public", "internal", "confidential", "finance_only"],
    "it":        ["public", "internal", "confidential", "it_only"],
    "executive": ["public", "internal", "confidential", "hr_only", "finance_only", "it_only"],
}


def _rrf_merge(doc_lists: list[list], k: int = 60) -> list:
    """Merge multiple ranked lists using Reciprocal Rank Fusion."""
    scores: dict = {}
    docs_by_hash: dict = {}
    for docs in doc_lists:
        for rank, d in enumerate(docs):
            # Use chunk identity to dedupe identical chunks across queries
            chunk_idx = d.metadata.get("chunk_index")
            if chunk_idx is not None:
                ch = f"{d.metadata.get('doc_id')}_{chunk_idx}"
            else:
                ch = d.page_content[:200]
            if ch not in docs_by_hash:
                docs_by_hash[ch] = d
            scores[ch] = scores.get(ch, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [docs_by_hash[ch] for ch, _ in ranked]


def _apply_metadata_boost(query: str, docs: list) -> list:
    """If the query mentions a doc_id, boost that doc."""
    import re
    doc_id_pattern = re.compile(r"\b[A-Z]{2,10}-[A-Z]{2,10}-\d{3,4}\b")
    mentioned = set(doc_id_pattern.findall(query.upper()))
    if not mentioned:
        return docs

    boosted = []
    others = []
    for d in docs:
        if d.metadata.get("doc_id") in mentioned:
            boosted.append(d)
        else:
            others.append(d)
    return boosted + others


def retrieve_documents(
    query: str,
    user_role: str,
    user_departments: list[str] | None = None,
    k: int = 30,
    top_n: int = 10,
) -> list:
    allowed = ROLE_CLEARANCE.get(user_role, ["public"])
    filter = models.Filter(
        must=[
            FieldCondition(key="metadata.access_level",
                           match=MatchAny(any=allowed)),
        ],
        should=[
            FieldCondition(key="metadata.roles",
                           match=MatchAny(any=[user_role])),
            FieldCondition(key="metadata.department",
                           match=MatchAny(any=user_departments or [])),
        ],
    )
    vs = get_vectorstore()
    retriever = vs.as_retriever(
        search_kwargs={"k": k, "filter": filter}
    )

    # Multi-query expansion
    queries = expand_query(query)

    # Retrieve for each query
    doc_lists = []
    for q in queries:
        try:
            doc_lists.append(retriever.invoke(q))
        except Exception as e:
            logger.warning("Retrieval failed for variant %r: %s", q, e)

    # Merge by RRF (also dedupes)
    merged = _rrf_merge(doc_lists)

    # Metadata boost
    merged = _apply_metadata_boost(query, merged)

    # Rerank to top_n
    return rerank(query, merged, top_n=top_n)
