import logging
import os
import re
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

DOC_ID_RE = re.compile(r"\b[A-Z]{2,10}-[A-Z]{2,10}-\d{3,4}\b")
MIN_RERANK_SCORE = float(os.environ.get("MIN_RERANK_SCORE", "0.05"))
MAX_RERANK_CANDIDATES = 30


def _rrf_merge(doc_lists: list[list], k: int = 60) -> list:
    """Merge multiple ranked lists using Reciprocal Rank Fusion."""
    scores: dict = {}
    docs_by_hash: dict = {}
    for docs in doc_lists:
        for rank, d in enumerate(docs):
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
    """If the query mentions a doc_id, boost that doc. (Must run AFTER rerank.)"""
    mentioned = set(DOC_ID_RE.findall(query.upper()))
    if not mentioned:
        return docs
    boosted = [d for d in docs if d.metadata.get("doc_id") in mentioned]
    others = [d for d in docs if d.metadata.get("doc_id") not in mentioned]
    return boosted + others


def _build_filter(user_role: str, user_departments, domains) -> models.Filter:
    allowed = ROLE_CLEARANCE.get(user_role)
    if not allowed:
        logger.warning("unknown role %r, falling back to public clearance", user_role)
        allowed = ["public"]

    must = [FieldCondition(key="metadata.access_level", match=MatchAny(any=allowed))]

    # Only departments the router picked; "public" always; "cross" / "crossdomain" for multi-domain queries
    if domains:
        depts = set(domains) | {"public"}
        if len(domains) > 1:
            depts.update(["cross", "crossdomain"])
        must.append(FieldCondition(key="metadata.department", match=MatchAny(any=sorted(depts))))

    # RBAC: the role must be listed on the doc OR the doc's department is one of the user's
    rbac_or = [FieldCondition(key="metadata.roles", match=MatchAny(any=[user_role]))]
    if user_departments:
        rbac_or.append(FieldCondition(key="metadata.department", match=MatchAny(any=list(user_departments))))
    must.append(models.Filter(should=rbac_or))

    return models.Filter(must=must)


def retrieve_documents(
    query: str,
    user_role: str,
    user_departments: list[str] | None = None,
    domains: list[str] | None = None,
    k: int = 15,
    top_n: int = 10,
) -> list:
    user_role = (user_role or "").strip().lower()
    qfilter = _build_filter(user_role, user_departments, domains)
    vs = get_vectorstore()
    retriever = vs.as_retriever(
        search_kwargs={"k": k, "filter": qfilter}
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

    if not doc_lists:
        logger.error("all retrieval attempts failed")
        return []

    # Merge by RRF (also dedupes), cap how many go to the slow reranker
    merged = _rrf_merge(doc_lists)[:MAX_RERANK_CANDIDATES]

    # Rerank (sets d.metadata["rerank_score"] between 0 and 1)
    ranked = rerank(query, merged, top_n=top_n)

    # Drop weak matches below the threshold
    kept = [d for d in ranked if d.metadata.get("rerank_score", 1.0) >= MIN_RERANK_SCORE]
    if not kept and ranked:
        logger.info(
            "all candidates below MIN_RERANK_SCORE=%.2f, retaining top matches as fallback",
            MIN_RERANK_SCORE,
        )
        kept = ranked[:3]

    logger.info(
        "retrieval domains=%s candidates=%d kept=%d top=%s",
        domains, len(merged), len(kept),
        [(d.metadata.get("doc_id"), round(d.metadata.get("rerank_score", 1.0), 2)) for d in ranked[:5]],
    )

    # Metadata boost applied AFTER rerank so it isn't undone
    return _apply_metadata_boost(query, kept)
