import logging

from app.config.model_config import get_model_info

logger = logging.getLogger("observability.cost")

def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """
    Estimate cost in USD. Returns 0.0 for unknown models.
    """
    info = get_model_info(model)
    cost = (
        tokens_in * info["input_per_million"] / 1_000_000
        + tokens_out * info["output_per_million"] / 1_000_000
    )
    return round(cost, 8)

def extract_usage(response) -> dict:
    """
    Extract token counts from a LangChain LLM response.
    Handles missing usage metadata gracefully (returns zeros).
    """
    tokens_in = 0
    tokens_out = 0
    try:
        # LangChain AIMessage has usage_metadata in v0.2+
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens_in = response.usage_metadata.get("input_tokens", 0)
            tokens_out = response.usage_metadata.get("output_tokens", 0)
        # Fallback for older versions using response_metadata
        elif hasattr(response, "response_metadata"):
            meta = response.response_metadata or {}
            usage = meta.get("token_usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
    except Exception as e:
        logger.warning("Failed to extract usage from response: %s", e)
    return {"tokens_in": tokens_in, "tokens_out": tokens_out}

def summarize_session(model: str, records: list[dict]) -> dict:
    """
    Given a list of {tokens_in, tokens_out} dicts, return total cost.
    Useful for batch analysis and eval.
    """
    total_in = sum(r.get("tokens_in", 0) for r in records)
    total_out = sum(r.get("tokens_out", 0) for r in records)
    return {
        "model": model,
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "total_cost_usd": estimate_cost(model, total_in, total_out),
        "call_count": len(records),
    }

