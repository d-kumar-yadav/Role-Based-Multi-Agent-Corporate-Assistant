import re

JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"you\s+are\s+now\s+(a|an|the)?",
    r"system\s+prompt",
    r"reveal\s+(your\s+)?(instructions|prompt|rules|system)",
    r"pretend\s+(to\s+be|you\s+are)",
    r"act\s+as\s+(a|an|if)",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[system\]",
    r"\[assistant\]",
]

_JAILBREAK_RE = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]

PROFANITY_PATTERNS = [
    r"\bf+u+c+k+\b",
    r"\bs+h+i+t+\b",
    r"\bb+i+t+c+h+\b",
    r"\ba+s+s+h+o+l+e+\b",
]

_PROFANITY_RE = [re.compile(p, re.IGNORECASE) for p in PROFANITY_PATTERNS]

def regex_check(query: str) -> dict:
    """
    Fast deterministic check for jailbreak patterns and profanity.
    Returns {"blocked": bool, "reason": str}
    """
    for pattern in _JAILBREAK_RE:
        if pattern.search(query):
            return {
                "blocked": True,
                "reason": f"jailbreak_pattern:{pattern.pattern[:40]}",
            }
    for pattern in _PROFANITY_RE:
        if pattern.search(query):
            return {
                "blocked": True,
                "reason": "profanity",
            }
    return {"blocked": False, "reason": ""}

