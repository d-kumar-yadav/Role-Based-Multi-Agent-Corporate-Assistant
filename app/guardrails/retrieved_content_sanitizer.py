import html
import logging
import re

logger = logging.getLogger("guardrails.retrieved_sanitizer")

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s+prompt",
    r"you\s+are\s+now\s+(a|an|the)?",
    r"\[system\]",
    r"\[assistant\]",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

def sanitize_chunk(text: str) -> str:
    """
    Strip injection patterns from a retrieved chunk.
    Also strips HTML comments and repeated blank lines.
    """
    for pattern in _INJECTION_RE:
        text = pattern.sub("[REDACTED]", text)
    # Strip HTML comments (often used to hide injection text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    # Collapse repeated blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def wrap_document(doc_id: str, text: str) -> str:
    """
    Wrap a chunk in <document> tags with the doc_id as source.
    Escapes text so any embedded tags are neutralized.
    """
    safe = html.escape(text)
    return f'<document source="{doc_id}">{safe}</document>'

def sanitize_and_wrap(doc_id: str, text: str) -> str:
    """Convenience: sanitize then wrap."""
    return wrap_document(doc_id, sanitize_chunk(text))

