import logging
import threading

logger = logging.getLogger("rag.reranker")

_lock = threading.Lock()
_model = None
MODEL_NAME = "BAAI/bge-reranker-base"

def _get_model():
    global _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import CrossEncoder
                _model = CrossEncoder(MODEL_NAME)
                logger.info("Reranker model loaded: %s", MODEL_NAME)
            except Exception as e:
                logger.exception("Failed to load reranker: %s", e)
                _model = None
    return _model

def rerank(query: str, docs: list, top_n: int = 5) -> list:
    """
    Rerank a list of LangChain Document objects by (query, content) relevance.
    Returns top_n docs, or the input list unchanged if the model fails.
    """
    if not docs:
        return docs

    model = _get_model()
    if model is None:
        logger.warning("Reranker unavailable, returning docs unranked")
        return docs[:top_n]

    try:
        pairs = [(query, d.page_content) for d in docs]
        scores = model.predict(pairs)
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]
    except Exception as e:
        logger.exception("Reranker failed during predict: %s", e)
        return docs[:top_n]

