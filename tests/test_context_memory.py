import os
import sys

# Ensure root directory is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.context_memory import (
    is_chat_summary_query,
    handle_chat_summary,
    is_why_explanation_query,
    explain_previous_refusal,
    needs_query_condensing,
    condense_query,
)

print("--- Test 1: Chat Summary Detection ---")
queries = [
    "summize this chat",
    "summarize this chat",
    "recap this chat",
    "give me a summary",
    "what is laptop policy",
]
for q in queries:
    print(f"{q!r} -> is_summary: {is_chat_summary_query(q)}")

print("\n--- Test 2: Why after Refusal Detection ---")
history_refusal = [
    {"role": "user", "content": "how to destroy the growth of my comapy"},
    {
        "role": "assistant",
        "content": "I'm sorry, but I can't help with that.",
        "meta": {"status": "blocked"},
    },
]
for q in ["why", "why?", "why not", "what is the limit"]:
    print(f"{q!r} -> is_why_explanation: {is_why_explanation_query(q, history_refusal)}")

expl = explain_previous_refusal("why", history_refusal)
print(f"Explanation: {expl}")

print("\n--- Test 3: Follow-up Condensation ---")
history_rag = [
    {"role": "user", "content": "how to reimburse laptop"},
    {
        "role": "assistant",
        "content": (
            "Laptop Reimbursement Process:\n"
            "1. Check IT compatibility (CROSS-EQUIP-001).\n"
            "2. Submit claim in Finance portal.\n"
            "3. Manager approval required if over INR 5,000."
        ),
        "meta": {"status": "answered"},
    },
]
for q in [
    "why does it need manager approval?",
    "what about for managers?",
    "what is the limit?",
]:
    needs = needs_query_condensing(q, history_rag)
    rewritten = condense_query(q, history_rag)
    print(f"Original: {q!r} -> Needs: {needs} -> Rewritten: {rewritten!r}")
