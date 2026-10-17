import logging
import threading

import numpy as np

logger = logging.getLogger("guardrails.dialog")

_lock = threading.Lock()
_model = None
_centroids = None
MODEL_NAME = "all-MiniLM-L6-v2"

DIALOG_INTENTS = {
    "greeting": [
        "hello", "hi", "hey", "hi there", "hello there",
        "good morning", "good afternoon", "good evening",
        "greetings", "howdy", "yo", "namaste",
    ],
    "help": [
        "help", "what can you do", "how do i use this",
        "what are your capabilities", "what can you help with",
        "how does this work", "what do you do",
    ],
    "goodbye": [
        "bye", "goodbye", "see you later", "see you",
        "thanks bye", "have a good day", "take care",
    ],
}

CANNED_RESPONSES = {
    "greeting": "Hello. I can help with HR, IT, and Finance questions. What do you need?",
    "help": "I can answer HR, IT, and Finance questions based on your access level. Try asking about leave policy, expense reimbursement, or VPN setup.",
    "goodbye": "Goodbye.",
}

SIMILARITY_THRESHOLD = 0.72

def _get_model():
    global _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(MODEL_NAME)
                logger.info("Dialog classifier model loaded: %s", MODEL_NAME)
            except Exception as e:
                logger.exception("Failed to load dialog model: %s", e)
                _model = None
    return _model

def _get_centroids():
    global _centroids
    if _centroids is not None:
        return _centroids
    model = _get_model()
    if model is None:
        return None
    centroids = {}
    for intent, examples in DIALOG_INTENTS.items():
        embeddings = model.encode(examples, normalize_embeddings=True)
        mean_vec = embeddings.mean(axis=0)
        centroids[intent] = mean_vec / np.linalg.norm(mean_vec)
    _centroids = centroids
    return _centroids

def check_dialog(query: str) -> dict:
    """
    Classify a query as greeting/help/goodbye if its embedding is close
    to one of the intent centroids. Returns:
        {"is_dialog": bool, "intent": str|None, "response": str|None}
    """
    model = _get_model()
    if model is None:
        return {"is_dialog": False, "intent": None, "response": None}

    try:
        query_emb = model.encode([query], normalize_embeddings=True)[0]
        centroids = _get_centroids()
        best_intent = None
        best_score = 0.0
        for intent, centroid in centroids.items():
            score = float(np.dot(query_emb, centroid))
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score >= SIMILARITY_THRESHOLD:
            return {
                "is_dialog": True,
                "intent": best_intent,
                "response": CANNED_RESPONSES[best_intent],
                "score": best_score,
            }
    except Exception as e:
        logger.exception("Dialog check failed: %s", e)

    return {"is_dialog": False, "intent": None, "response": None}
