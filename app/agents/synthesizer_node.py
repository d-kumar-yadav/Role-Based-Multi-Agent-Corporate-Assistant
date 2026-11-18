import logging
import re

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

logger = logging.getLogger("agents.synthesizer")

llm = ChatGroq(
    model=env_config.FIREWALL_MODEL,
    api_key=env_config.FIREWALL_GROQ_API_KEY,
    temperature=0,
    max_tokens=1500,
)

MAX_PARTIAL_CHARS = 2000
MAX_TOTAL_CHARS = 4000
NO_ANSWER = "I couldn't find this in the documents available to you."
CITATION_RE = re.compile(r"\(([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\)")
REFUSAL_MARKERS = ("I don't have access", "I couldn't find this", "INSUFFICIENT_CONTEXT")


def _truncate(text: str, limit: int) -> str:
    if not text or len(text) <= limit:
        return text or ""
    return text[:limit] + "... [truncated]"


def _is_refusal(p: dict) -> bool:
    return bool(p.get("refusal")) or any(m in str(p.get("answer", "")) for m in REFUSAL_MARKERS)


MERGE_PROMPT = """You are merging partial answers from multiple domain
agents into one coherent answer.

Rules:
1. Do NOT introduce facts not present in the partial answers.
2. Preserve all numbers, doc_ids, and policy details exactly.
3. Deduplicate overlapping content.
4. Keep every citation in the form (DOC-ID) at the end of the sentence it supports.
5. No conversational filler, greetings or closing offers.

Formatting rules (output is rendered as Markdown):
- Start with one short bold title line.
- Group content by topic. Use a numbered list for sequential steps and a
  bulleted list for facts or options. Start list items with a bold phrase.
- Leave a blank line between the title, each group and the closing note.
- Put exceptions or warnings in ONE final blockquote line, like:
  > **Note:** Claims after 60 days need Finance Head approval. (FIN-POLICY-001)

Query: {query}

Partial answers:
{partials}

Merged answer:"""


def _build_citations(doc_ids, retrieved_docs):
    meta = {}
    for d in retrieved_docs or []:
        if isinstance(d, dict) and d.get("doc_id") and d["doc_id"] not in meta:
            meta[d["doc_id"]] = {
                "doc_id": d["doc_id"],
                "title": d.get("title", ""),
                "version": d.get("version", ""),
                "section": d.get("section") or None,
            }
    return [meta[i] for i in doc_ids if i in meta]


def _result(state: dict, answer: str, candidate_ids: list) -> dict:
    """Cite only documents that appear in the final answer text."""
    cited = sorted(set(CITATION_RE.findall(answer)) & set(candidate_ids)) or sorted(set(candidate_ids))
    return {
        "answer": answer,
        "synthesized_doc_ids": cited,
        "citations": _build_citations(cited, state.get("retrieved_docs", [])),
    }


def synthesizer_node(state: dict) -> dict:
    query = state.get("query", "")
    partials = state.get("partial_answers", [])
    if not isinstance(partials, list):
        partials = []

    # Only this turn's partials; older turns stay in state but are ignored
    valid = [p for p in partials if isinstance(p, dict) and p.get("turn_id") == state.get("turn_id")]

    latest_by_domain = {}
    for p in valid:
        dom = p.get("domain")
        latest_by_domain[dom.strip() if isinstance(dom, str) and dom.strip() else "unknown"] = p
    current = list(latest_by_domain.values())

    if not current:
        return {"answer": NO_ANSWER, "synthesized_doc_ids": [], "citations": []}

    answering = [p for p in current if not _is_refusal(p)]
    if not answering:
        return {"answer": NO_ANSWER, "synthesized_doc_ids": [], "citations": []}

    def ids_of(p):
        ids = p.get("doc_ids", [])
        return [i for i in ids if isinstance(i, str)] if isinstance(ids, list) else []

    # One real answer: pass through, no LLM call, formatting untouched
    if len(answering) == 1:
        p = answering[0]
        return _result(state, str(p.get("answer", "")), ids_of(p))

    blocks = [
        f"[{str(p.get('domain') or 'unknown').strip()}]\n{_truncate(str(p.get('answer', '')).strip(), MAX_PARTIAL_CHARS)}"
        for p in answering
    ]
    partials_text = "\n\n".join(blocks)[:MAX_TOTAL_CHARS]
    all_ids = sorted({i for p in answering for i in ids_of(p)})

    logger.info("synthesizer: partials=%d merged=%d chars=%d", len(partials), len(answering), len(partials_text))

    try:
        chain = PromptTemplate.from_template(MERGE_PROMPT) | llm
        merged = chain.invoke({"query": query, "partials": partials_text}).content.strip()
    except Exception:
        logger.exception("synthesizer merge failed; falling back to joined answers")
        merged = "\n\n".join(str(p.get("answer", "")).strip() for p in answering)

    return _result(state, merged, all_ids)