import logging
import os

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

logger = logging.getLogger("agents.synthesizer")

llm = ChatGroq(
    model=os.environ.get("FIREWALL_MODEL", "openai/gpt-oss-20b"),
    api_key=os.environ.get("FIREWALL_GROQ_API_KEY"),
    temperature=0,
    max_tokens=1500,
)

MAX_PARTIAL_CHARS = 2000
MAX_TOTAL_CHARS = 4000


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"


MERGE_PROMPT = """You are merging partial answers from multiple domain
agents into one coherent answer.

Rules:
1. Do NOT introduce facts not present in the partial answers.
2. Preserve all numbers, doc_ids, and policy details exactly.
3. Deduplicate overlapping content.
4. Skip partial answers that are refusals (contain 'I don't have access'
   or 'INSUFFICIENT_CONTEXT') UNLESS all partials are refusals — in
   which case return a single combined refusal.
5. Cite the doc_id for every factual claim.
6. No conversational filler.

Query: {query}

Partial answers:
{partials}

Merged answer:"""


def _build_citations(doc_ids: list[str], retrieved_docs: list[dict]) -> list[dict]:
    """Join doc_ids against retrieved_docs to build Citation-shaped dicts."""
    meta_by_id = {}
    if isinstance(retrieved_docs, list):
        for d in retrieved_docs:
            if isinstance(d, dict):
                did = d.get("doc_id")
                if did and did not in meta_by_id:
                    meta_by_id[did] = {
                        "doc_id": did,
                        "title": d.get("title", ""),
                        "version": d.get("version", ""),
                        "section": d.get("section") or None,
                    }
    return [meta_by_id[did] for did in doc_ids if did in meta_by_id]


def synthesizer_node(state: dict) -> dict:
    partials = state.get("partial_answers", [])
    query = state.get("query", "")

    if not partials or not isinstance(partials, list):
        return {
            "answer": "I cannot answer this query.",
            "synthesized_doc_ids": [],
            "citations": [],
        }

    valid_partials = [p for p in partials if isinstance(p, dict)]
    if not valid_partials:
        return {
            "answer": "I cannot answer this query.",
            "synthesized_doc_ids": [],
            "citations": [],
        }

    # Deduplicate accumulated partials across turns by domain, retaining latest
    latest_by_domain = {}
    for p in valid_partials:
        dom = p.get("domain")
        if isinstance(dom, str) and dom.strip():
            key = dom.strip()
        else:
            key = "unknown"
        latest_by_domain[key] = p
    current_partials = list(latest_by_domain.values())

    # Single partial — pass through unchanged
    if len(current_partials) == 1:
        doc_ids = current_partials[0].get("doc_ids", [])
        if not isinstance(doc_ids, list):
            doc_ids = []
        raw_ans = current_partials[0].get("answer", "")
        ans = raw_ans if isinstance(raw_ans, str) else str(raw_ans or "")
        return {
            "answer": ans,
            "synthesized_doc_ids": doc_ids,
            "citations": _build_citations(doc_ids, state.get("retrieved_docs", [])),
        }

    # All refusals — return a single combined refusal
    refusal_markers = ("I don't have access", "INSUFFICIENT_CONTEXT")
    all_refusals = all(
        any(m in str(p.get("answer", "")) for m in refusal_markers)
        for p in current_partials
    )
    if all_refusals:
        return {
            "answer": "I don't have access to the information needed to answer this query.",
            "synthesized_doc_ids": [],
            "citations": [],
        }

    # Calculate raw character count before bounding
    raw_chars = sum(len(str(p.get("answer", ""))) for p in current_partials)

    # Format each partial bounded by MAX_PARTIAL_CHARS
    formatted_blocks = []
    for p in current_partials:
        dom = str(p.get("domain") or "unknown").strip()
        ans_val = p.get("answer", "")
        ans_text = ans_val if isinstance(ans_val, str) else str(ans_val or "")
        truncated_ans = _truncate(ans_text.strip(), MAX_PARTIAL_CHARS)
        formatted_blocks.append(f"[{dom}]\n{truncated_ans}")

    partials_text = "\n\n".join(formatted_blocks)

    # Enforce strict hard cap on partials_text
    if len(partials_text) > MAX_TOTAL_CHARS:
        partials_text = partials_text[:MAX_TOTAL_CHARS]

    logger.info(
        "synthesizer_input_bounded: raw_partials=%d deduplicated_partials=%d raw_chars=%d bounded_chars=%d",
        len(partials),
        len(current_partials),
        raw_chars,
        len(partials_text),
    )

    prompt = PromptTemplate.from_template(MERGE_PROMPT)
    chain = prompt | llm
    response = chain.invoke({"query": query, "partials": partials_text})

    all_doc_ids = sorted({
        did for p in current_partials
        if isinstance(p.get("doc_ids"), list)
        for did in p["doc_ids"]
        if isinstance(did, str)
    })
    return {
        "answer": response.content,
        "synthesized_doc_ids": all_doc_ids,
        "citations": _build_citations(all_doc_ids, state.get("retrieved_docs", [])),
    }
