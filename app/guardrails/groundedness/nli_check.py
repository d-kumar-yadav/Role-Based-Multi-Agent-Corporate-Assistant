import logging
import re
import threading
import numpy as np

logger = logging.getLogger("guardrails.groundedness.nli")

_lock = threading.Lock()
_model = None
_model_failed = False
MODEL_NAME = "cross-encoder/nli-deberta-v3-base"

TOP_CHUNKS = 3     # chunks compared against each claim
CHUNK_CHARS = 900  # keeps each pair under the 512-token limit
CHUNK_OVERLAP = 150
ENTAIL_MIN = 0.5

_TAG_RE = re.compile(r"</?document[^>]*>")
_CITE_RE = re.compile(r"\(?\b[A-Z]{2,10}-[A-Z]{2,10}-\d{3,4}\b\)?")
_WORD_RE = re.compile(r"[a-z0-9]+")


def _get_model():
    global _model, _model_failed
    if _model is not None or _model_failed:  # don't retry after a failure
        return _model
    with _lock:
        if _model is None and not _model_failed:
            try:
                from sentence_transformers import CrossEncoder
                _model = CrossEncoder(MODEL_NAME, max_length=512)
                logger.info("NLI model loaded: %s", MODEL_NAME)
            except Exception as e:
                logger.exception("Failed to load NLI model: %s", e)
                _model_failed = True
    return _model


def warmup():
    """Call once at startup (in a background thread) so no user waits for the load."""
    _get_model()


def _split_context(context: str) -> list[str]:
    text = _TAG_RE.sub("\n\n", context or "")
    chunks = []
    for part in re.split(r"\n{2,}", text):
        part = part.strip()
        if not part:
            continue
        step = CHUNK_CHARS - CHUNK_OVERLAP
        for i in range(0, len(part), step):
            chunks.append(part[i:i + CHUNK_CHARS])
            if i + CHUNK_CHARS >= len(part):
                break
    return chunks


def _top_chunks(claim: str, chunks: list[str]) -> list[str]:
    words = set(_WORD_RE.findall(claim.lower()))
    ranked = sorted(chunks, key=lambda c: len(words & set(_WORD_RE.findall(c.lower()))), reverse=True)
    return ranked[:TOP_CHUNKS]


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max(axis=1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=1, keepdims=True)


def check_claims(claims: list[str], context: str) -> dict:
    """
    Stage 2: NLI entailment check.
    Each claim is compared with the most relevant chunks of the context.
    Returns {"entailment_ratio": float, "contradiction_count": int, "neutral_count": int, "per_claim": [...]}
    """
    if not claims:
        return {"entailment_ratio": 1.0, "contradiction_count": 0, "neutral_count": 0, "per_claim": []}

    model = _get_model()
    chunks = _split_context(context)
    if model is None or not chunks:
        # Fail-open: cannot check, assume grounded
        return {
            "entailment_ratio": 1.0,
            "contradiction_count": 0,
            "neutral_count": 0,
            "per_claim": [],
            "error": "model_unavailable" if model is None else "empty_context",
        }

    clean = [_CITE_RE.sub("", c).strip() for c in claims]
    pairs, owners = [], []
    for i, claim in enumerate(clean):
        for chunk in _top_chunks(claim, chunks):
            pairs.append((chunk, claim))
            owners.append(i)

    # DeBERTa NLI label order: [contradiction, entailment, neutral]; predict() returns logits
    probs = _softmax(np.asarray(model.predict(pairs, batch_size=16)))
    owners = np.asarray(owners)

    entail_n = contra_n = neutral_n = 0
    per_claim = []

    for i, claim in enumerate(claims):
        p = probs[owners == i]
        entail, contra = float(p[:, 1].max()), float(p[:, 0].max())
        if entail >= ENTAIL_MIN:
            label, conf = "entailment", entail
            entail_n += 1
        elif contra >= 0.5 and entail < 0.2:
            label, conf = "contradiction", contra
            contra_n += 1
        else:
            label, conf = "neutral", float(p[:, 2].max())
            neutral_n += 1

        per_claim.append({"claim": claim[:120], "label": label, "confidence": round(conf, 3)})

    return {
        "entailment_ratio": entail_n / len(claims),
        "contradiction_count": contra_n,
        "neutral_count": neutral_n,
        "per_claim": per_claim,
    }
