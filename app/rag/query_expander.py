import hashlib
import logging
import os
from functools import lru_cache

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger("rag.query_expander")

EXPAND_PROMPT = """Generate 2 alternative phrasings of the user's 
question. Each phrasing should preserve the meaning but use different 
words. Output ONLY the 2 questions, one per line, no numbering, no 
bullets, no extra text.

Original: {query}
"""

@lru_cache(maxsize=500)
def _cache_key(query: str) -> str:
    return hashlib.sha256(query.lower().strip().encode()).hexdigest()

def expand_query(query: str) -> list[str]:
    """
    Return [original, alt1, alt2]. Falls back to [original] on any error.
    Uses an LRU cache so repeated queries don't re-hit the LLM.
    """
    # Cheap path: if we've seen this query, return the cached expansion
    cache = _expansion_cache
    key = _cache_key(query)
    if key in cache:
        return cache[key]

    try:
        from app.config import env_config
        llm = ChatGroq(
            model=env_config.FIREWALL_MODEL,
            temperature=0.3,
            api_key=os.environ.get("FIREWALL_GROQ_API_KEY"),
        )
        prompt = PromptTemplate.from_template(EXPAND_PROMPT)
        chain = prompt | llm
        response = chain.invoke({"query": query})
        lines = [l.strip() for l in response.content.splitlines() if l.strip()]
        # Keep only the first 2 non-empty lines, drop any that match the original
        alts = []
        for line in lines:
            line = line.lstrip("0123456789.-) ").strip()
            if line and line.lower() != query.lower() and line not in alts:
                alts.append(line)
            if len(alts) == 2:
                break
    except Exception as e:
        logger.warning("Query expansion failed: %s", e)
        alts = []

    result = [query] + alts
    cache[key] = result
    return result

_expansion_cache: dict = {}

