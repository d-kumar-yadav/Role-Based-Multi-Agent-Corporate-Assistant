import re

CITATION_PATTERN = re.compile(r"\[([A-Z]{2,10}-[A-Z]{2,10}-\d{3,4})\]")
BARE_ID_PATTERN = re.compile(r"\b([A-Z]{2,10}-[A-Z]{2,10}-\d{3,4})\b")

def extract_citations(answer: str) -> list[str]:
    """Extract doc_id references from the answer text."""
    bracketed = CITATION_PATTERN.findall(answer)
    bare = BARE_ID_PATTERN.findall(answer)
    seen = set()
    result = []
    for doc_id in bracketed + bare:
        if doc_id not in seen:
            seen.add(doc_id)
            result.append(doc_id)
    return result

def verify_citations(answer: str, retrieved_doc_ids: set[str]) -> dict:
    """
    Stage 1: deterministic citation existence check.
    Returns {"valid": bool, "cited_ids": [...], "fabricated_ids": [...], "reason": str}
    """
    cited = extract_citations(answer)
    fabricated = [doc_id for doc_id in cited if doc_id not in retrieved_doc_ids]

    if fabricated:
        return {
            "valid": False,
            "cited_ids": cited,
            "fabricated_ids": fabricated,
            "reason": "fabricated_citation",
        }

    # If answer contains a factual-sounding claim but no citations, flag it.
    # Heuristic: answer length > 120 chars AND contains at least one digit.
    has_facts = len(answer) > 120 and any(c.isdigit() for c in answer)
    if has_facts and not cited:
        return {
            "valid": False,
            "cited_ids": [],
            "fabricated_ids": [],
            "reason": "missing_citations",
        }

    return {
        "valid": True,
        "cited_ids": cited,
        "fabricated_ids": [],
        "reason": "",
    }

