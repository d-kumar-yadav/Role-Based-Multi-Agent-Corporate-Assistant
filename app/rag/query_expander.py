import hashlib
import logging
import os
import re
import threading
from collections import OrderedDict

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger("rag.query_expander")

EXPAND_PROMPT = """Generate 2 alternative phrasings of the user's 
question. Each phrasing should preserve the meaning but use different 
words. Output ONLY the 2 questions, one per line, no numbering, no 
bullets, no extra text.

Original: {query}
"""

EXPANSION_ENABLED = os.environ.get("QUERY_EXPANSION", "1") == "1"
CACHE_MAX = 500
_DOC_ID_RE = re.compile(r"\b[A-Z]{2,10}-[A-Z]{2,10}-\d{3,4}\b")

_expansion_cache: "OrderedDict[str, list[str]]" = OrderedDict()
_cache_lock = threading.Lock()
_llm = None
_llm_lock = threading.Lock()


def _cache_key(query: str) -> str:
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()


def _get_llm():
    global _llm
    if _llm is None:
        with _llm_lock:
            if _llm is None:
                _llm = ChatGroq(
                    model=os.environ.get("EXPAND_MODEL") or os.environ.get("ROUTER_MODEL") or "openai/gpt-oss-20b",
                    temperature=0.3,
                    api_key=os.environ.get("FIREWALL_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY"),
                    timeout=5,
                    max_retries=0,
                )
    return _llm


def expand_query(query: str) -> list[str]:
    """
    Return [original, alt1, alt2]. Falls back to [original] on any error.
    Uses a bounded LRU cache so repeated queries don't re-hit the LLM.
    """
    query = (query or "").strip()
    if not query or not EXPANSION_ENABLED or _DOC_ID_RE.search(query.upper()):
        return [query]

    key = _cache_key(query)
    with _cache_lock:
        if key in _expansion_cache:
            _expansion_cache.move_to_end(key)
            return list(_expansion_cache[key])

    try:
        chain = PromptTemplate.from_template(EXPAND_PROMPT) | _get_llm()
        response = chain.invoke({"query": query})
        alts = []
        for line in response.content.splitlines():
            line = re.sub(r"^\s*(?:\d+[.)]|[-*•])\s+", "", line).strip().strip("\"'")
            if line and line.lower() != query.lower() and line not in alts:
                alts.append(line)
            if len(alts) == 2:
                break
    except Exception as e:
        logger.warning("Query expansion failed: %s", e)
        return [query]

    result = [query] + alts
    with _cache_lock:
        _expansion_cache[key] = result
        while len(_expansion_cache) > CACHE_MAX:
            _expansion_cache.popitem(last=False)
    return list(result)
