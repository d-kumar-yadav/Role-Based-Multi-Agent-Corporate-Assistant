import logging

logger = logging.getLogger("agents.validator")


def validator_node(state: dict) -> dict:
    """
    Pass-through validator.

    Previously ran an LLM to polish tone and formatting. Removed in
    Phase 8D to reduce per-query LLM calls from 5 to 2. Domain agents
    already produce clean, well-formatted answers.

    Groundedness verification still happens in output_checks.py
    (deterministic + NLI-based), so removing the LLM polish does not
    weaken the safety model.
    """
    answer = state.get("answer") or ""
    return {"final_answer": answer}
