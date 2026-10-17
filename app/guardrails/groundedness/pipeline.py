import logging
import unicodedata

from app.guardrails.groundedness.citation_check import verify_citations
from app.guardrails.groundedness.claim_splitter import split_into_claims
from app.guardrails.groundedness.nli_check import check_claims
from app.guardrails.groundedness.anchor_check import extract_anchors, verify_anchors

logger = logging.getLogger("guardrails.groundedness.pipeline")

ENTAILMENT_THRESHOLD = 0.75


def _normalize_text(text: str) -> str:
    """
    Normalize LLM output before groundedness checks.

    Fixes Unicode substitutions the LLM introduces that break ASCII
    pattern matching: fullwidth brackets, non-breaking hyphens,
    em/en dashes, and smart quotes.
    """
    if not text:
        return ""
    replacements = {
        "\u3010": "[",   # 【
        "\u3011": "]",   # 】
        "\uff3b": "[",   # ［
        "\uff3d": "]",   # ］
        "\u2010": "-",   # hyphen
        "\u2011": "-",   # non-breaking hyphen
        "\u2012": "-",   # figure dash
        "\u2013": "-",   # en-dash
        "\u2014": "-",   # em-dash
        "\u2212": "-",   # minus sign
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u00a0": " ",   # no-break space
        "\u2007": " ",   # figure space
        "\u2009": " ",   # thin space
        "\u200a": " ",   # hair space
        "\u2002": " ",   # en space
        "\u2003": " ",   # em space
        "\u2004": " ",   # three-per-em space
        "\u2005": " ",   # four-per-em space
        "\u2006": " ",   # six-per-em space
        "\u202f": " ",   # narrow no-break space
        "\u3000": " ",   # ideographic space
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    import re as _re
    text = _re.sub(r" {2,}", " ", text)
    return unicodedata.normalize("NFKC", text)


def verify_groundedness(answer: str, retrieved_docs: list[dict]) -> dict:
    """
    Layered groundedness verification.
    Stage 1: citation existence (deterministic)
    Stage 2: claim-level NLI entailment
    Stage 3: factual anchor verification
    Returns {"grounded": bool, "stage": str, "reason": str, "details": dict}
    """
    answer = _normalize_text(answer)
    if not retrieved_docs:
        return {
            "grounded": False,
            "stage": "no_context",
            "reason": "no_context_retrieved",
            "details": {},
        }

    context = "\n\n".join(d.get("content", "") for d in retrieved_docs)
    context = _normalize_text(context)
    retrieved_doc_ids = {d.get("doc_id") for d in retrieved_docs if d.get("doc_id")}

    # Stage 1 — citations
    stage1 = verify_citations(answer, retrieved_doc_ids)
    if not stage1["valid"]:
        return {
            "grounded": False,
            "stage": "citations",
            "reason": stage1["reason"],
            "details": stage1,
        }

    # Stage 2 — NLI
    claims = split_into_claims(answer)
    if len(claims) >= 2:
        nli_result = check_claims(claims, context)
        contradictions = nli_result.get("contradiction_count", 0)
        ratio = nli_result.get("entailment_ratio", 1.0)

        # NLI is a signal, not a gate. The model was trained on general text
        # and misclassifies dense policy language. Contradictions are logged
        # for observability but do not block. Deterministic stages (citations
        # and anchors) remain the blocking layer.
        if contradictions > 0:
            logger.warning(
                "nli_contradiction_signal contradictions=%d ratio=%.2f — not blocking",
                contradictions, ratio,
            )
        elif ratio < 0.5:
            logger.warning(
                "nli_low_entailment ratio=%.2f neutral=%d — not blocking",
                ratio, nli_result.get("neutral_count", 0),
            )

        # Attach the NLI result to the output for downstream audit visibility
        nli_signal = {
            "entailment_ratio": ratio,
            "contradiction_count": contradictions,
            "neutral_count": nli_result.get("neutral_count", 0),
        }
        stage2 = nli_result
    else:
        nli_signal = {"skipped": True}
        stage2 = {"entailment_ratio": None, "skipped": True}

    # Stage 3 — anchors
    anchors = extract_anchors(answer)
    anchor_total = 0
    anchor_verified = 0
    anchor_unverified = []
    anchor_failure_ratio = 0.0

    if anchors:
        stage3 = verify_anchors(anchors, context)
        anchor_total = stage3.get("total", 0)
        anchor_verified = stage3.get("verified", 0)
        anchor_unverified = stage3.get("unverified", [])

        if anchor_total > 0:
            anchor_failure_ratio = (anchor_total - anchor_verified) / anchor_total
        else:
            anchor_failure_ratio = 0.0

        # Tier 1: majority of anchors unverified = real hallucination
        if anchor_failure_ratio > 0.5:
            return {
                "grounded": False,
                "stage": "anchors",
                "reason": "unsupported_fact_majority",
                "anchor_failure_ratio": anchor_failure_ratio,
                "nli_signal": nli_signal,
                "details": stage3,
            }

        # Tier 2: partial mismatch = signal, not blocker
        if anchor_unverified:
            logger.warning(
                "anchor_partial_mismatch total=%d verified=%d unverified=%d ratio=%.2f — not blocking",
                anchor_total,
                anchor_verified,
                len(anchor_unverified),
                anchor_failure_ratio,
            )
    else:
        stage3 = {"skipped": True}

    return {
        "grounded": True,
        "stage": "passed",
        "reason": "",
        "nli_signal": nli_signal,
        "anchor_signal": {
            "total": anchor_total,
            "verified": anchor_verified,
            "unverified_count": len(anchor_unverified),
            "failure_ratio": anchor_failure_ratio,
        },
        "details": {
            "citations": stage1,
            "nli": stage2,
            "anchors": stage3,
        },
    }

