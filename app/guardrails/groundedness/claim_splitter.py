import re

REFUSAL_PHRASES = (
    "i don't have access",
    "i cannot answer",
    "insufficient_context",
    "no relevant documents",
)

GREETINGS = (
    "hello", "hi", "sure", "of course", "certainly",
    "thank you", "thanks", "you're welcome",
)

TRANSITIONS = (
    "let me explain", "in summary", "to summarize",
    "here is", "below is", "the following",
)

def split_into_claims(answer: str) -> list[str]:
    """
    Split the answer into atomic claims suitable for NLI.
    Filters greetings, transitions, and refusals.
    Returns a list of claim strings.
    """
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())

    claims = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(s) < 15:
            continue
        lower = s.lower()
        if any(g in lower for g in GREETINGS):
            continue
        if any(t in lower for t in TRANSITIONS):
            continue
        if any(r in lower for r in REFUSAL_PHRASES):
            continue
        claims.append(s)
    return claims

