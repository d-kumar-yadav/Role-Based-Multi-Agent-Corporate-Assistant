import logging
import threading

import numpy as np

logger = logging.getLogger("rag.reranker")

_lock = threading.Lock()
_model = None
_model_failed = False
MODEL_NAME = "BAAI/bge-reranker-base"


def _get_model():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    with _lock:
        if _model is None and not _model_failed:
            try:
                from sentence_transformers import CrossEncoder
                _model = CrossEncoder(MODEL_NAME, max_length=512)
                logger.info("Reranker model loaded: %s", MODEL_NAME)
            except Exception as e:
                logger.exception("Failed to load reranker: %s", e)
                _model_failed = True
    return _model


def warmup():
    """Call at startup in a background thread."""
    _get_model()


def _to_probs(scores) -> np.ndarray:
    s = np.asarray(scores, dtype=float)
    if s.size and (s.min() < 0 or s.max() > 1):  # raw logits -> sigmoid
        s = 1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))
    return s


def rerank(query: str, docs: list, top_n: int = 5) -> list:
    """
    Rerank a list of LangChain Document objects by (query, content) relevance.
    Returns top_n docs (each with metadata["rerank_score"]), or the input
    list unchanged if the model fails.
    """
    if not docs:
        return docs

    model = _get_model()
    if model is None:
        logger.warning("Reranker unavailable, returning docs unranked")
        return docs[:top_n]

    try:
        pairs = [(query, d.page_content) for d in docs]
        scores = _to_probs(model.predict(pairs, batch_size=16))
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        out = []
        for d, s in ranked[:top_n]:
            d.metadata["rerank_score"] = float(s)
            out.append(d)
        return out
    except Exception as e:
        logger.exception("Reranker failed during predict: %s", e)
        return docs[:top_n]

# 1. Where did docs come from before reaching the reranker?

# Before this function was even called, Qdrant (the vector database) already searched and retrieved these documents ordered by vector similarity.

# docs[0] = Qdrant's #1 best match
# docs[1] = Qdrant's #2 best match
# docs[2] = Qdrant's #3 best match
# ... and so on.

# The reranker is just a secondary optimization layer (a "smart second pass") to re-order them even better.

# Python's zip() function works just like a zipper on a jacket, matching one tooth from the left side with one tooth from the right side:

# Left side: docs = [Doc1, Doc2, Doc3] (List of multiple documents)
# Right side: scores = [2.4, -1.8, 9.1] (List of multiple scores)

# When you do zip(docs, scores):
# Doc1  <── pairs with ──>  2.4   ──> (Doc1,  2.4)
# Doc2  <── pairs with ──> -1.8   ──> (Doc2, -1.8)
# Doc3  <── pairs with ──>  9.1   ──> (Doc3,  9.1)

# The result of zip(docs, scores) is a collection of pairs:
# [
#     (Doc1,  2.4),
#     (Doc2, -1.8),
#     (Doc3,  9.1)
# ]

# key=lambda x: x[1]:Tells Python's sorted(): "In each pair (doc, score), sort using index 1 (the score), not the document."
# reverse=True: Sorts from highest score to lowest score (descending order).

# ranked[:top_n]:
# If top_n = 2, it cuts the list to keep only the top 2 matches:
# [(DocB, 8.72), (DocC, -1.20)]

# for d, _ in ...:
# Unpacks each tuple. d is the Document object, and _ is a Python convention meaning "ignore the numerical score, we don't need it anymore".
# [d for ...]:
# Puts just the Document objects back into a clean list. Final Returned Value:[DocB, DocC]

# [DocA, DocB, DocC]  +  query
#          │
#          ▼ (Line 1: pairs)
# [(query, textA), (query, textB), (query, textC)]
#          │
#          ▼ (Line 2: model.predict)
# [-4.15, 8.72, -1.20]
#          │
#          ▼ (Line 3: zip + sorted by score)
# [(DocB, 8.72), (DocC, -1.20), (DocA, -4.15)]
#          │
#          ▼ (Line 4: take top_n & drop score)
# [DocB, DocC]  <-- Passed to LLM for final answer!

# 1. Bi-Encoder (What Qdrant & Embedding Models Use)
# "Bi" means Two. The Query and the Document are processed completely separately.

# 2. Cross-Encoder (What the Reranker Uses)
# "Cross" means Cross-Attention. The Query and the Document are fed into the neural network together at the exact same time.
