import logging
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer import AnalyzerEngine
from .pii_patterns import analyzer
from app.guardrails.groundedness.pipeline import verify_groundedness

anonymizer = AnonymizerEngine()
logger = logging.getLogger("guardrails.output")


def redact_pii(text: str) -> tuple[str, bool, list]:
    """
    Redact PII from the output text. Returns (safe_text, pii_found, detected_entities)
    """
    entities_to_redact = [
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "US_SSN",
        "US_BANK_NUMBER",
        "IBAN_CODE",
        "IP_ADDRESS"
    ]
    try:
        results = analyzer.analyze(text=text, entities=entities_to_redact, language='en')
        anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
        pii_found = len(results) > 0
        detected_entities = list(set([r.entity_type for r in results]))
        anonymized_text = anonymized_result.text if (anonymized_result and anonymized_result.text) else text
        return anonymized_text, pii_found, detected_entities
    except Exception as exc:
        logger.warning(
            "pii_redaction_failed chars=%d error=%s — returning original",
            len(text), exc.__class__.__name__,
        )
        return text, False, []


def check_toxicity(text: str) -> bool:
    """
    Simple keyword-based toxicity filter.
    Returns True if toxic.
    """
    toxic_keywords = ["idiot", "stupid", "shut up", "dumb"]
    text_lower = text.lower()
    for kw in toxic_keywords:
        if kw in text_lower:
            return True
    return False


def run_output_guardrails(answer: str, retrieved_docs: list[dict]) -> dict:
    """
    Run all output checks.
    """
    # 1. Toxicity Check
    if check_toxicity(answer):
        return {"blocked": True, "reason": "Toxicity detected in output", "final_answer": "The generated response was blocked due to safety policies."}

    # 2. Groundedness Check (Signal only, never blocks)
    groundedness = verify_groundedness(answer, retrieved_docs)
    grounded = groundedness.get("grounded", True)

    if not grounded:
        logger.warning(
            "groundedness_signal stage=%s reason=%s nli=%s anchors=%s — not blocking",
            groundedness.get("stage"),
            groundedness.get("reason"),
            groundedness.get("nli_signal"),
            groundedness.get("anchor_signal"),
        )

    # 3. PII Redaction (mutation, not a block)
    safe_answer, pii_found, detected_entities = redact_pii(answer)
    final_answer = safe_answer

    if not final_answer and answer:
        # Redaction or any downstream step silently emptied the response.
        # Do not return empty when the input answer was non-empty.
        logger.error(
            "output_guardrails_emptied_answer input_chars=%d",
            len(answer),
        )
        final_answer = answer

    # Groundedness never blocks. It is recorded as a signal in the audit log.
    # Deterministic safety layers (regex, PII, firewall, RBAC, citations)
    # remain the blocking layer.
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
    # This is the final dictionary sent back to main.py. The most important part here is "blocked": False.

# Notice that even if we found highly sensitive PII, we do not block the request. Why? Because we successfully mutated the text by scrubbing out the PII and replacing it with safe tags. The safe_answer is now perfectly fine to show the user. We just pass the reason along so main.py can secretly write it to the audit_log.jsonl for the security team to see!
