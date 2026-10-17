import logging
import threading

logger = logging.getLogger("guardrails.groundedness.nli")

_lock = threading.Lock()
_model = None
MODEL_NAME = "cross-encoder/nli-deberta-v3-base"

def _get_model():
    global _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import CrossEncoder
                _model = CrossEncoder(MODEL_NAME)
                logger.info("NLI model loaded: %s", MODEL_NAME)
            except Exception as e:
                logger.exception("Failed to load NLI model: %s", e)
                _model = None
    return _model

def check_claims(claims: list[str], context: str) -> dict:
    """
    Stage 2: NLI entailment check.
    For each claim, asks: is this claim entailed by the context?
    Returns {"entailment_ratio": float, "contradiction_count": int,
             "neutral_count": int, "per_claim": [...]}
    """
    if not claims:
        return {
            "entailment_ratio": 1.0,
            "contradiction_count": 0,
            "neutral_count": 0,
            "per_claim": [],
        }

    model = _get_model()
    if model is None:
        # Fail-open: cannot check, assume grounded
        return {
            "entailment_ratio": 1.0,
            "contradiction_count": 0,
            "neutral_count": 0,
            "per_claim": [],
            "error": "model_unavailable",
        }

    # DeBERTa NLI label order: [contradiction, entailment, neutral]
    pairs = [(context, claim) for claim in claims]
    scores = model.predict(pairs)

    entailment_count = 0
    contradiction_count = 0
    neutral_count = 0
    per_claim = []

    for i, claim in enumerate(claims):
        row = scores[i]
        # row is a 3-element array
        label_idx = int(row.argmax())
        confidence = float(row[label_idx])
        label = ["contradiction", "entailment", "neutral"][label_idx]

        if label == "entailment" and confidence >= 0.5:
            entailment_count += 1
        elif label == "contradiction" and confidence >= 0.5:
            contradiction_count += 1
        else:
            neutral_count += 1

        per_claim.append({
            "claim": claim[:120],
            "label": label,
            "confidence": round(confidence, 3),
        })

    total = len(claims)
    return {
        "entailment_ratio": entailment_count / total,
        "contradiction_count": contradiction_count,
        "neutral_count": neutral_count,
        "per_claim": per_claim,
    }

