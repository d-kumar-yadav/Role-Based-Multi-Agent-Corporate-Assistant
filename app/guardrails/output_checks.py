import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer import AnalyzerEngine
from .pii_patterns import analyzer
from app.config import env_config

anonymizer = AnonymizerEngine()
logger = logging.getLogger("guardrails.output")


def check_groundedness(context: str, answer: str) -> bool:
    """
    Check if the answer is grounded in the retrieved context.
    """
    # If the agent is refusing to answer because it couldn't find it in the context,
    # that is a SAFE response. We don't need to run a hallucination check on a refusal!
    if "I don't have access" in answer or "Access Denied" in answer or "I cannot answer this based on the retrieved" in answer:
        return True

    if not context.strip():
        # If there's no context and it's not a standard refusal, it's a hallucination
        return False

    try:
        llm = ChatGroq(model=env_config.MODEL, temperature=0)
        prompt = PromptTemplate.from_template(
            "Does this answer follow only from this context?\n\nContext: {context}\n\nAnswer: {answer}\n\nRespond with only Yes or No."
        )
        response = prompt | llm
        result = response.invoke({"context": context, "answer": answer})

        return "yes" in result.content.strip().lower()
    except Exception as e:
        logger.exception("Groundedness check failed, failing open: %s", e)
        return True  # Fallback on error


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
    results = analyzer.analyze(text=text, entities=entities_to_redact, language='en')
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    # This is the Digital Black Marker. We hand the original text and the detective's results over to the anonymizer. It goes to those exact character locations and replaces the sensitive data with safe placeholder tags. (For example, it changes "Call me at 555-1234" to "Call me at <PHONE_NUMBER>").

    pii_found = len(results) > 0
    detected_entities = list(set([r.entity_type for r in results]))

    return anonymized_result.text, pii_found, detected_entities


def check_toxicity(text: str) -> bool:
    """
    Simple keyword-based toxicity filter or LLM check.
    Returns True if toxic.
    """
    toxic_keywords = ["idiot", "stupid", "shut up", "dumb"]
    text_lower = text.lower()
    for kw in toxic_keywords:
        if kw in text_lower:
            return True

    # check with LLM
    try:
        llm = ChatGroq(model=env_config.MODEL, temperature=0)
        prompt = PromptTemplate.from_template(
            "Is the following text toxic, offensive, or harmful? Respond with only Yes or No.\n\nText: {text}"
        )
        response = (prompt | llm).invoke({"text": text})
        return "yes" in response.content.strip().lower()
    except Exception as e:
        logger.exception("LLM toxicity check failed, falling back to keyword result only: %s", e)
        return False


def run_output_guardrails(context: str, answer: str) -> dict:
    """
    Run all output checks.
    """
    # 1. Toxicity Check
    if check_toxicity(answer):
        return {"blocked": True, "reason": "Toxicity detected in output", "final_answer": "The generated response was blocked due to safety policies."}

    # 2. Groundedness Check
    if not check_groundedness(context, answer):
        return {"blocked": True, "reason": "Answer is not grounded in context (Hallucination)", "final_answer": "I am sorry, but I cannot confidently answer this based on the retrieved context."}

    # 3. PII Redaction (mutation, not a block)
    safe_answer, pii_found, detected_entities = redact_pii(answer)

    reason = f"PII Redacted: {', '.join(detected_entities)}" if pii_found else ""
    return {"blocked": False, "reason": reason, "final_answer": safe_answer}
    # This is the final dictionary sent back to main.py. The most important part here is "blocked": False.

# Notice that even if we found highly sensitive PII, we do not block the request. Why? Because we successfully mutated the text by scrubbing out the PII and replacing it with safe tags. The safe_answer is now perfectly fine to show the user. We just pass the reason along so main.py can secretly write it to the audit_log.jsonl for the security team to see!
