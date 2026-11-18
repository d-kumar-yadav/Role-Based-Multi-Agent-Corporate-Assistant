import logging
import re
import threading

import numpy as np

logger = logging.getLogger("guardrails.dialog")

_lock = threading.Lock()
_model = None
_model_failed = False
_centroids = None
_ready = threading.Event()  # set once the model and centroids are fully built
MODEL_NAME = "all-MiniLM-L6-v2"

DIALOG_INTENTS = {
    "greeting": [
        "hello", "hi", "hey", "hi there", "hello there",
        "good morning", "good afternoon", "good evening",
        "greetings", "howdy", "yo", "namaste",
        "how are you", "how are u",
    ],
    "help": [
        "help", "what can you do", "how do i use this",
        "what are your capabilities", "what can you help with",
        "how does this work", "what do you do",
        "who are you", "what is your name",
    ],
    "goodbye": [
        "bye", "goodbye", "see you later", "see you",
        "thanks bye", "have a good day", "take care",
    ],
    "closing": [
        "ok thanks", "thank you", "thanks", "that's all", "nothing else",
        "i am good", "no thanks", "no thank you",
    ],
    "just_checking": [
        "just checking", "i was just checking", "im just checking",
    ],
}

CANNED_RESPONSES = {
    "greeting": "Hello. I can help with HR, IT, and Finance questions. What do you need?",
    "help": "I can answer HR, IT, and Finance questions based on your access level. Try asking about leave policy, expense reimbursement, or VPN setup.",
    "goodbye": "Goodbye.",
    "closing": "You're welcome. Reach out anytime you need help.",
    "just_checking": "No problem. I'm here whenever you need HR, IT, or Finance help.",
}

SIMILARITY_THRESHOLD = 0.65
MAX_DIALOG_WORDS = 6

NOT_DIALOG = {"is_dialog": False, "intent": None, "response": None}


def _normalize(text: str) -> str:
    text = re.sub(r"[^\w\s']", "", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


# exact-match lookup, answers "hi" / "bye" instantly without the model
_EXACT = {_normalize(e): intent for intent, exs in DIALOG_INTENTS.items() for e in exs}

# pattern match, catches spelling variants like "hii", "heyyy", "thx", "byeee"
_FAST_PATTERNS = [
    ("greeting", re.compile(r"^(h+i+|h+e+y+|h+e+l+o+|hiya|y+o+|howdy|namaste|good (morning|afternoon|evening)( (all|everyone|team))?)( there| all| team)?$")),
    ("goodbye",  re.compile(r"^(b+y+e+( bye)?|goodbye|see (you|ya)( later)?|take care|cya)$")),
    ("closing",  re.compile(r"^(thanks+|thank you( so much| very much)?|thx|ty|ok(ay)? thanks?|that'?s all|nothing else|no thanks?|no thank you)$")),
]


def _fast_match(text: str):
    intent = _EXACT.get(text)
    if intent:
        return intent
    for name, pattern in _FAST_PATTERNS:
        if pattern.match(text):
            return name
    return None


def _get_model():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    with _lock:
        if _model is None and not _model_failed:
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(MODEL_NAME, device="cpu")
                logger.info("Dialog classifier model loaded: %s", MODEL_NAME)
            except Exception as e:
                logger.exception("Failed to load dialog model: %s", e)
                _model_failed = True
    return _model


def _get_centroids():
    global _centroids
    if _centroids is not None:
        return _centroids
    model = _get_model()
    if model is None:
        return None
    with _lock:
        if _centroids is None:
            centroids = {}
            for intent, examples in DIALOG_INTENTS.items():
                embeddings = model.encode(examples, normalize_embeddings=True)
                mean_vec = embeddings.mean(axis=0)
                centroids[intent] = mean_vec / np.linalg.norm(mean_vec)
            _centroids = centroids
    return _centroids


def _load_in_background():
    if _get_centroids() is not None:
        _ready.set()


def start_warmup():
    """Build centroids (called inside background warmup thread)."""
    _load_in_background()


def check_dialog(query: str) -> dict:
    """
    Step 1: instant keyword / pattern match (no model).
    Step 2: centroid similarity, only if the model is already loaded.
    Returns: {"is_dialog": bool, "intent": str|None, "response": str|None}
    """
    text = _normalize(query)
    if not text or len(text.split()) > MAX_DIALOG_WORDS:
        return dict(NOT_DIALOG)

    intent = _fast_match(text)  # step 1: instant regex / exact lookup
    if intent:
        return {"is_dialog": True, "intent": intent, "response": CANNED_RESPONSES[intent], "score": 1.0}

    if not _ready.is_set():  # model still loading in background -> never block the user
        return dict(NOT_DIALOG)

    try:  # step 2: centroids
        query_emb = _model.encode([text], normalize_embeddings=True)[0]
        best_intent = None
        best_score = 0.0
        for name, centroid in _centroids.items():
            score = float(np.dot(query_emb, centroid))
            if score > best_score:
                best_score = score
                best_intent = name

        if best_score >= SIMILARITY_THRESHOLD:
            return {
                "is_dialog": True,
                "intent": best_intent,
                "response": CANNED_RESPONSES[best_intent],
                "score": best_score,
            }
    except Exception as e:
        logger.exception("Dialog check failed: %s", e)

    return dict(NOT_DIALOG)
