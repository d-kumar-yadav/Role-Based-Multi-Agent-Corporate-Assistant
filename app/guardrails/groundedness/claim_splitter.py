import re

REFUSAL_PHRASES = (
    "i don't have access",
    "i cannot answer",
    "i couldn't find this",
    "insufficient_context",
    "no relevant documents",
)

# Filler is only checked at the START of a sentence, as whole words
_FILLER_START = re.compile(
    r"^(hello|hi|hey|sure|of course|certainly|thank you|thanks|you're welcome|"
    r"let me explain|in summary|to summarize|here is|here are|below is|the following)\b",
    re.IGNORECASE,
)

_CITATION = re.compile(r"\(?\b[A-Z]{2,10}-[A-Z]{2,10}-\d{3,4}\b\)?")
_CITATION_ONLY = re.compile(r"^(?:\s*\(?[A-Z]{2,10}-[A-Z]{2,10}-\d{3,4}\)?[\s.,;]*)+$")
_LIST_MARKER = re.compile(r"^\s*(?:>\s*)?(?:[-*•]\s+|\d+[.)]\s+)?")
_BOLD_TITLE = re.compile(r"^\s*\*\*[^*]+\*\*\s*$")


def split_into_claims(answer: str) -> list[str]:
    """
    Split the answer into atomic claims suitable for NLI.
    Handles Markdown lists, blockquotes and trailing (DOC-ID) citations.
    Filters titles, greetings, transitions, and refusals.
    """
    raw = []
    for line in (answer or "").splitlines():
        if not line.strip() or _BOLD_TITLE.match(line):
            # empty line or bold title
            continue
        line = _LIST_MARKER.sub("", line)
        line = re.sub(r"\*{1,2}|__", "", line).strip()  # remove bold / italic markers

        for s in re.split(r"(?<=[.!?])\s+", line):
            s = s.strip()
            if not s:
                continue
            # a citation that landed after the full stop belongs to the previous claim
            if _CITATION_ONLY.match(s):
                if raw:
                    raw[-1] += " " + s
                continue
            raw.append(s)

    claims = []
    for c in raw:
        text_only = _CITATION.sub("", c).strip()
        if len(text_only) < 15:
            continue
        if _FILLER_START.match(text_only):
            continue
        if any(r in text_only.lower() for r in REFUSAL_PHRASES):
            continue
        claims.append(c)

    return claims
