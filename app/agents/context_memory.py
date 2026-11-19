import logging
import re
from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import env_config

logger = logging.getLogger("agents.context_memory")

# Fast LLM client for context condensation and summarization
_condenser_llm = None


def _get_condenser_llm():
    global _condenser_llm
    if _condenser_llm is None:
        try:
            from langchain_groq import ChatGroq
            _condenser_llm = ChatGroq(
                model=env_config.ROUTER_MODEL,
                api_key=env_config.FIREWALL_GROQ_API_KEY,
                temperature=0.0,
                timeout=4,
                max_retries=0,
                max_tokens=150,
            )
        except Exception as e:
            logger.warning("Could not initialize condenser LLM: %s", e)
    return _condenser_llm


# ── 1. CHAT SUMMARY DETECTION & HANDLING ──────────────────────────────────────

_SUMMARY_PATTERNS = [
    re.compile(r"^(?:can\s+you\s+)?(?:please\s+)?(?:summarize|summarise|summize|summary|recap|review)\s*(?:of\s+)?(?:this|the|our)?\s*(?:chat|conversation|discussion|thread)?\??$", re.IGNORECASE),
    re.compile(r"^(?:what\s+did\s+we\s+(?:talk\s+about|discuss)|what\s+have\s+we\s+discussed|recap\s+everything|give\s+me\s+a\s+summary)\??$", re.IGNORECASE),
    re.compile(r"^(?:summarize|summarise|summize|recap)\b", re.IGNORECASE),
]


def is_chat_summary_query(query: str) -> bool:
    """Check if the user is asking to summarize or recap the current chat thread."""
    q = (query or "").strip().lower()
    for pattern in _SUMMARY_PATTERNS:
        if pattern.search(q):
            return True
    return False


def handle_chat_summary(history_messages: List[Dict]) -> str:
    """Generate a clean, structured summary of the ongoing chat thread."""
    # Filter to real conversation turns
    meaningful_turns = [
        m for m in history_messages
        if isinstance(m, dict) and m.get("content") and m.get("role") in ("user", "assistant")
    ]

    if not meaningful_turns:
        return (
            "**Conversation Summary**\n\n"
            "There is no previous conversation history in this thread to summarize yet. "
            "Feel free to ask any questions regarding company HR, IT, or Finance policies!"
        )

    # Format history for summarization
    formatted_lines = []
    for msg in meaningful_turns[-10:]:
        role = "Employee" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "").strip()
        # Truncate overly long assistant replies to preserve prompt space
        if len(content) > 250:
            content = content[:250] + "..."
        formatted_lines.append(f"{role}: {content}")

    history_str = "\n".join(formatted_lines)

    llm = _get_condenser_llm()
    if llm:
        try:
            prompt = (
                "You are Meridian Copilot, an enterprise AI assistant for HR, Finance, and IT.\n"
                "The employee asked you to summarize the ongoing conversation thread.\n"
                "Provide a concise, professional markdown summary of what the employee asked "
                "and what key policy answers or outcomes were provided.\n\n"
                "Formatting:\n"
                "**Conversation Summary**\n"
                "Use bullet points for each topic discussed.\n\n"
                f"Conversation:\n{history_str}\n\n"
                "Summary:"
            )
            resp = llm.invoke([HumanMessage(content=prompt)]).content.strip()
            if resp:
                return resp
        except Exception as e:
            logger.warning("LLM chat summary failed, using fallback: %s", e)

    # Deterministic fallback summary
    summary_lines = ["**Conversation Summary**\n"]
    for i, msg in enumerate(meaningful_turns):
        if msg.get("role") == "user":
            q_text = msg.get("content", "").strip()
            summary_lines.append(f"- **Query**: {q_text}")
    return "\n".join(summary_lines)


# ── 2. REFUSAL EXPLANATION DETECTION & HANDLING ───────────────────────────────

_WHY_PATTERNS = [
    re.compile(r"^(why|why\?|why\s+not\??|why\s+is\s+that\??|why\s+can't\s+you\??|why\s+was\s+it\s+blocked\??|reason\??)$", re.IGNORECASE),
    re.compile(r"^why\s+(?:did\s+you|can't\s+you|was\s+this|was\s+it|is\s+it)\b", re.IGNORECASE),
]

_REFUSAL_INDICATORS = [
    "can't help with that",
    "cannot help",
    "cannot comply",
    "corporate assistant for hr, finance, and it",
    "couldn't find this in the documents",
    "safety policies",
    "not authorized",
    "declined",
    "blocked",
]


def is_why_explanation_query(query: str, history_messages: List[Dict]) -> bool:
    """Check if the user is asking 'why' immediately following an assistant refusal or block."""
    q = (query or "").strip().lower()
    matches_why = any(p.search(q) for p in _WHY_PATTERNS)
    if not matches_why:
        return False

    if not history_messages:
        return False

    # Find the last assistant message
    last_assistant_msg = None
    for msg in reversed(history_messages):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg
            break

    if not last_assistant_msg:
        return False

    # Check if last assistant message was a refusal or block
    meta = last_assistant_msg.get("meta") or {}
    status = meta.get("status", "")
    content = (last_assistant_msg.get("content") or "").lower()

    if status in ("blocked", "refused", "denied"):
        return True

    return any(ind in content for ind in _REFUSAL_INDICATORS)


def explain_previous_refusal(query: str, history_messages: List[Dict]) -> str:
    """Explain why the previous request was declined or blocked."""
    last_user_msg = ""
    last_assistant_msg = ""
    last_status = "blocked"

    for msg in reversed(history_messages):
        if not last_assistant_msg and msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "")
            meta = msg.get("meta") or {}
            last_status = meta.get("status", "blocked")
        elif not last_user_msg and msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
        if last_assistant_msg and last_user_msg:
            break

    user_lower = last_user_msg.lower()
    asst_lower = last_assistant_msg.lower()

    # Case 1: Malicious / Harm / Jailbreak / Toxicity
    if any(k in user_lower for k in ["destroy", "hack", "bypass", "exploit", "kill", "harm", "bitch", "attack", "sabotage"]):
        return (
            "Your previous request was declined by the security firewall because corporate acceptable use "
            "policies strictly prohibit instructions or queries aimed at damaging company assets, sabotaging "
            "operations, or using abusive language. Meridian Copilot is here to assist you with legitimate HR, "
            "Finance, and IT operational questions."
        )

    # Case 2: Document Not Found / RBAC clearance
    if "couldn't find this in the documents" in asst_lower:
        return (
            "The previous query could not be answered because the requested subject is not present in the "
            "documents authorized for your role and department clearance. If this policy is necessary for "
            "your work, please reach out to your manager or IT support for permissions."
        )

    # Case 3: Off-topic general advice (medical, general geography, competitors)
    if "corporate assistant" in asst_lower or "personal" in asst_lower or "medical" in asst_lower:
        return (
            "I declined the previous question because Meridian Copilot is configured exclusively for internal "
            "enterprise workflows (HR policies, IT support, and Finance procedures). I am not authorized to "
            "provide external general knowledge, competitor analyses, or personal medical/legal advice."
        )

    # General explanation
    return (
        "Your previous request was restricted under company governance and safety rules. "
        "I am authorized to assist with internal HR, Finance, and IT policy inquiries."
    )


# ── 3. QUERY CONDENSATION (FOLLOW-UP RESOLUTION) ──────────────────────────────

_PRONOUNS_AND_DEICTICS = {
    "it", "its", "this", "that", "these", "those", "they", "them", "their",
    "he", "she", "him", "her", "such", "same", "above", "mentioned", "step",
}

_FOLLOW_UP_STARTERS = (
    "why", "how come", "what about", "how about", "and for", "can you explain",
    "who approves", "what is the limit", "how much", "how long", "can an intern",
    "can i", "is it", "does it", "where do i", "who do i", "what if", "tell me more",
)


def needs_query_condensing(query: str, history_messages: List[Dict]) -> bool:
    """Check if the incoming query relies on context from previous turns."""
    if not history_messages:
        return False

    q_strip = (query or "").strip().lower()
    if is_chat_summary_query(q_strip):
        return False
    if is_why_explanation_query(q_strip, history_messages):
        return False

    words = re.findall(r"\b[a-z0-9'-]+\b", q_strip)
    if not words:
        return False

    # Very short queries (< 6 words) almost always depend on context
    if len(words) <= 5:
        return True

    # Contains deictic pronouns
    if any(w in _PRONOUNS_AND_DEICTICS for w in words):
        return True

    # Starts with common follow-up phrases
    if any(q_strip.startswith(starter) for starter in _FOLLOW_UP_STARTERS):
        return True

    return False


def _heuristic_topic_enrichment(query: str, history_messages: List[Dict]) -> str:
    """Extract key subject from previous turns to ground short follow-up questions when LLM is unavailable."""
    prev_user_q = ""
    for msg in reversed(history_messages):
        if msg.get("role") == "user" and msg.get("content"):
            prev_user_q = msg.get("content", "").strip()
            break
    
    if not prev_user_q:
        return query

    # Strip conversational question starters
    clean_topic = re.sub(
        r"^(?:how\s+(?:to|do\s+i|can\s+i)|what\s+(?:is\s+the|are\s+the|is)|tell\s+me\s+about|can\s+you|please)\s+",
        "",
        prev_user_q,
        flags=re.IGNORECASE,
    ).strip(" ?.")

    if not clean_topic or len(clean_topic) < 3:
        return query

    # If the topic words aren't already in the follow-up query, enrich with context
    topic_words = set(re.findall(r"\w+", clean_topic.lower()))
    query_words = set(re.findall(r"\w+", query.lower()))
    if not (topic_words & query_words):
        return f"{query.strip().rstrip('?.')} regarding {clean_topic}?"
    return query


def condense_query(query: str, history_messages: List[Dict]) -> str:
    """
    Rewrite an ambiguous follow-up query into a self-contained standalone query
    using recent conversation history.
    """
    if not needs_query_condensing(query, history_messages):
        return query

    llm = _get_condenser_llm()
    if not llm:
        return _heuristic_topic_enrichment(query, history_messages)

    # Collect the last 2-3 turns (user + assistant)
    recent = []
    for m in history_messages[-6:]:
        if isinstance(m, dict) and m.get("content"):
            role = "Employee" if m.get("role") == "user" else "Assistant"
            text = m.get("content", "").strip()
            if len(text) > 300:
                text = text[:300] + "..."
            recent.append(f"{role}: {text}")

    if not recent:
        return query

    history_str = "\n".join(recent)

    prompt = (
        "You are an expert query rewriting assistant for an enterprise RAG assistant.\n"
        "Given the recent conversation history and an employee's follow-up question, rewrite "
        "the follow-up question into a single, complete, standalone question.\n\n"
        "Rules:\n"
        "1. Replace pronouns (it, this, that, they) and relative references (step 3, approval, the limit) "
        "with explicit topics, nouns, and entities from the conversation history.\n"
        "2. Keep the exact domain context (e.g., laptop reimbursement, leave policy, travel expense).\n"
        "3. Do NOT answer the question. Output ONLY the standalone rewritten question.\n"
        "4. Do NOT include quotes or preambles.\n\n"
        f"Conversation History:\n{history_str}\n\n"
        f"Follow-up Question: {query}\n\n"
        "Standalone Question:"
    )

    try:
        rewritten = llm.invoke([HumanMessage(content=prompt)]).content.strip()
        rewritten = re.sub(r"^(?:Standalone Question|Rewritten Question):\s*", "", rewritten, flags=re.IGNORECASE)
        rewritten = rewritten.strip(' "\'\n')
        if rewritten and len(rewritten) > 2:
            logger.info("condensed_query original=%r -> rewritten=%r", query, rewritten)
            return rewritten
    except Exception as e:
        logger.warning("Query condensation failed (%s), using heuristic fallback", e)

    return _heuristic_topic_enrichment(query, history_messages)


# ── 4. FORMATTING CHAT HISTORY FOR AGENT PROMPTS ─────────────────────────────

def format_chat_history_for_prompt(history_messages: List[Dict], max_messages: int = 6) -> str:
    """Format recent turns for inclusion in the domain agent's prompt context."""
    if not history_messages:
        return ""

    meaningful = [
        m for m in history_messages
        if isinstance(m, dict) and m.get("content") and m.get("role") in ("user", "assistant")
    ]
    if not meaningful:
        return ""

    lines = []
    for m in meaningful[-max_messages:]:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = m.get("content", "").strip()
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{role}: {content}")

    return "\n".join(lines)
