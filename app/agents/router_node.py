import logging
import re
from typing import List, Literal
from pydantic import BaseModel
from langchain_groq import ChatGroq
from app.config import env_config

logger = logging.getLogger("agents.router")

llm = ChatGroq(model=env_config.ROUTER_MODEL, temperature=0, timeout=4, max_retries=0)

# ── keyword tables ────────────────────────────────────────────────────────────
KEYWORD_ROUTING = {
    "hr":      ["leave", "vacation", "compensation", "salary", "recruit",
                "hiring", "onboard", "benefit", "handbook",
                "posh", "grievance", "performance", "promotion",
                "maternity", "paternity", "sabbatical", "attendance",
                "appraisal", "wfh", "work from home"],
    "finance": ["expense", "reimburse", "refund", "budget", "revenue",
                "invoice", "vendor", "procurement", "audit", "tax",
                "purchase order", "per diem", "travel", "entertainment",
                "corporate card", "po", "claim", "payslip"],
    "it":      ["vpn", "laptop", "monitor", "password", "software",
                "access", "security", "runbook", "ticket", "asset",
                "network", "device", "on-call", "headset", "docking",
                "wifi"],
}

# A rule fires only when EVERY group has at least one match.
# So "laptop is slow" stays IT only, and "reimburse my laptop" becomes IT + Finance.
CROSS_DOMAIN_RULES = [
    ({"it", "finance"}, [["reimburse", "refund", "purchase", "buy", "claim", "cost", "price"],
                         ["laptop", "monitor", "device", "equipment", "docking", "headset"]]),
    ({"hr", "it"},      [["onboard", "offboard", "exit", "new joiner"]]),
    ({"hr", "finance"}, [["payroll", "bonus"]]),
]

ALL_DOMAINS = ["hr", "finance", "it"]


# ── word-boundary match with common endings (expenses, reimbursed, onboarding) ─
def _hit(query: str, kw: str) -> bool:
    kw = re.escape(kw.strip())
    if len(kw) <= 2:                                   # "po" must be a whole word
        pattern = rf"\b{kw}\b"
    else:                                              # allow s / es / ed / d / ing / ment(s)
        pattern = rf"\b{kw}(?:s|es|ed|d|ing|ment|ments)?\b"
    return re.search(pattern, query) is not None


# ── LLM fallback (only called when keywords miss) ────────────────────────────
_ROUTER_PROMPT = """You are a routing classifier for a corporate AI assistant.
Decide which internal departments can answer the employee's question.

Departments:
- hr      : leave, benefits, hiring, onboarding, conduct policies, performance reviews
- finance : expenses, reimbursements, budgets, invoices, procurement, tax, payslips
- it      : devices, accounts, passwords, VPN, software licenses, security, tickets

Respond ONLY with the names of the applicable departments (e.g. "hr" or "finance, it").
If none apply, respond "none".

Query: {query}"""


def _llm_route(query: str) -> set:
    """Call the LLM classifier and return a set of domain strings."""
    try:
        reply = llm.invoke(_ROUTER_PROMPT.format(query=query)).content.lower()
        found = set(re.findall(r"\b(hr|finance|it)\b", reply))
        return found
    except Exception as e:
        logger.warning("LLM routing failed: %s", e)
        return set()


# ── main node ─────────────────────────────────────────────────────────────────
def router_node(state: dict) -> dict:
    query = (state.get("standalone_query") or state.get("query") or "").lower()

    # 1. Fast keyword pass
    matched: set = set()
    for domain, keywords in KEYWORD_ROUTING.items():
        if any(_hit(query, kw) for kw in keywords):
            matched.add(domain)

    # 2. Cross-domain promotion (all trigger groups must match)
    for pair_domains, groups in CROSS_DOMAIN_RULES:
        if all(any(_hit(query, kw) for kw in group) for group in groups):
            matched.update(pair_domains)

    # 3. LLM fallback — only when keywords found nothing
    source = "keywords"
    if not matched:
        matched = _llm_route(query)
        source = "llm"

    # 4. Still nothing -> search all domains; the retrieval relevance cutoff drops junk
    if not matched:
        matched = set(ALL_DOMAINS)
        source = "default_all"

    logger.info("routed domains=%s via=%s", sorted(matched), source)
    return {"domains": sorted(matched)}
