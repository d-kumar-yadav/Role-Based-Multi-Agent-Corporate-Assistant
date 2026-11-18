import html
import logging
import re
import unicodedata

logger = logging.getLogger("guardrails.retrieved_sanitizer")

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"(reveal|show|print|repeat)\s+(your\s+|the\s+)?system\s+prompt",
    # only when it tries to reassign the AI's role, not "you are now eligible"
    r"you\s+are\s+now\s+(an?\s+)?(ai|assistant|chatbot|bot|model|agent|different|new|unrestricted)\b",
    r"new\s+instructions\s*:",
    r"\[system\]",
    r"\[assistant\]",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)  
_TAG_START_RE = re.compile(r"<(?=[/!?A-Za-z])")  # '<' that could open a tag


def sanitize_chunk(text: str, doc_id: str = "") -> str:
    """Strip injection patterns, hidden text and comments from a retrieved chunk."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _ZERO_WIDTH_RE.sub("", text)   #removea any space 
    text = _COMMENT_RE.sub("", text)          # remove comment

    hits = 0
    for pattern in _INJECTION_RE:
        text, n = pattern.subn("[REDACTED]", text)
        # subn("[REDACTED]", text) replaces any matching injection phrase with [REDACTED] and returns (new_text, count_of_replacements).
        hits += n
    if hits:
        logger.warning("injection_patterns_redacted doc_id=%s count=%d", doc_id, hits)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def wrap_document(doc_id: str, text: str) -> str:
    """Wrap a chunk in <document> tags. Only tag-like '<' is neutralised, so
    '&', quotes, and comparisons like '< 5000' stay readable."""
    safe = _TAG_START_RE.sub("&lt;", text)
    return f'<document source="{html.escape(doc_id, quote=True)}">{safe}</document>' 
# wrap all the thing inside a documnet tag so thta llm undersatnd as text not intstruction



def sanitize_and_wrap(doc_id: str, text: str) -> str:
    return wrap_document(doc_id, sanitize_chunk(text, doc_id))