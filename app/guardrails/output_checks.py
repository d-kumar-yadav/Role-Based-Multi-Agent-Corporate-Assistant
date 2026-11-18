import logging
import os
import re
from presidio_anonymizer import AnonymizerEngine
from .pii_patterns import analyzer
from app.guardrails.groundedness.pipeline import verify_groundedness

anonymizer = AnonymizerEngine()
logger = logging.getLogger("guardrails.output")

_BASE_ENTITIES = [
    "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "US_SSN", "US_BANK_NUMBER", "IBAN_CODE", "IP_ADDRESS"
]
_EXTRA_ENTITIES = ["IN_PAN", "IN_AADHAAR"]

try:
    _supported = set(analyzer.get_supported_entities(language="en"))
except Exception:
    _supported = set()

ENTITIES_TO_REDACT = _BASE_ENTITIES + [e for e in _EXTRA_ENTITIES if e in _supported]

COMPANY_EMAIL_DOMAIN = os.environ.get("COMPANY_EMAIL_DOMAIN", "").lower().lstrip("@")
BLOCK_FABRICATED_CITATIONS = True
BLOCK_MESSAGE = "The generated response was blocked due to safety policies."

_TOXIC_RE = re.compile(r"\b(idiot|stupid|shut up|dumb)\b", re.IGNORECASE)
_REFUSAL_MARKERS = ("i couldn't find this", "i don't have access", "i cannot answer")


class RedactionError(Exception):
    pass


def redact_pii(text: str) -> tuple[str, bool, list]:
    """
    Redact PII from the output text.
    Returns (safe_text, pii_found, detected_entities)
    Raises RedactionError if redaction cannot be completed (caller must not show the raw text).
    """
    try:
        results = analyzer.analyze(text=text, entities=ENTITIES_TO_REDACT, language='en')
        if COMPANY_EMAIL_DOMAIN:
            results = [
                r for r in results
                if not (r.entity_type == "EMAIL_ADDRESS" and text[r.start:r.end].lower().endswith("@" + COMPANY_EMAIL_DOMAIN))
            ]
        if not results:
            return text, False, []

        anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
        detected_entities = list(set([r.entity_type for r in results]))
        logger.info("pii_detected count=%d entities=%s", len(results), detected_entities)
        return anonymized_result.text, True, detected_entities
    except Exception as exc:
        logger.warning("pii_redaction_failed chars=%d error=%s", len(text), exc.__class__.__name__)
        raise RedactionError from exc


def check_toxicity(text: str) -> bool:
    """
    Simple keyword-based toxicity filter.
    Returns True if toxic.
    """
    return bool(_TOXIC_RE.search(text))


def _is_refusal(answer: str) -> bool:
    low = answer.lower()
    return len(answer) < 250 and any(m in low for m in _REFUSAL_MARKERS)


def _blocked(reason: str, message: str = BLOCK_MESSAGE) -> dict:
    return {"blocked": True, "reason": reason, "final_answer": message}


def run_output_guardrails(answer: str, retrieved_docs: list[dict]) -> dict:
    """
    Run all output checks.
    """
    answer = (answer or "").strip()
    if not answer:
        return _blocked("empty_answer", "I couldn't generate an answer. Please try rephrasing your question.")

    # 1. Toxicity Check
    if check_toxicity(answer):
        return _blocked("Toxicity detected in output")

    # 2. Groundedness Check (signal, except fabricated citations)
    if _is_refusal(answer):
        groundedness = {"grounded": True, "stage": "skipped_refusal"}
    else:
        groundedness = verify_groundedness(answer, retrieved_docs)

    grounded = groundedness.get("grounded", True)

    # A cited doc_id that was never retrieved is invented, so block it
    if (BLOCK_FABRICATED_CITATIONS and
            groundedness.get("stage") == "citations" and
            groundedness.get("reason") == "fabricated_citation"):
        fake = groundedness.get("details", {}).get("fabricated_ids", [])
        logger.warning("fabricated_citation_blocked ids=%s", fake)
        return _blocked("fabricated_citation: " + ", ".join(fake))

    if not grounded:
        logger.warning(
            "groundedness_signal stage=%s reason=%s nli=%s anchors=%s — not blocking",
            groundedness.get("stage"),
            groundedness.get("reason"),
            groundedness.get("nli_signal"),
            groundedness.get("anchor_signal"),
        )

    # 3. PII Redaction (mutation, not a block)
    try:
        safe_answer, pii_found, detected_entities = redact_pii(answer)
    except RedactionError:
        return _blocked("pii_redaction_failed")

    if not safe_answer.strip():
        logger.error("output_guardrails_emptied_answer input_chars=%d", len(answer))
        return _blocked("answer_emptied_by_redaction")

    final_answer = safe_answer

    # Groundedness never blocks (except fabricated citations above). It is recorded as a signal in the audit log.
    reason_parts = []
    if pii_found:
        reason_parts.append("PII Redacted: " + ", ".join(detected_entities))
    if not grounded:
        reason_parts.append("ungrounded_signal:" + str(groundedness.get("stage")))

    reason = "; ".join(reason_parts)

    return {
        "blocked": False,
        "reason": reason,
        "final_answer": final_answer,
        "groundedness_signal": {
            "grounded": grounded,
            "stage": groundedness.get("stage"),
            "reason": groundedness.get("reason"),
            "nli_signal": groundedness.get("nli_signal"),
            "anchor_signal": groundedness.get("anchor_signal"),
        },
    }
