"""
Central catalog of models and their pricing.
All prices are USD per 1 million tokens.
"""

MODEL_CATALOG = {
    "llama-3.3-70b-versatile": {
        "provider": "groq",
        "input_per_million": 0.59,
        "output_per_million": 0.79,
        "context_window": 128000,
        "tier": "large",
    },
    "llama-3.1-8b-instant": {
        "provider": "groq",
        "input_per_million": 0.05,
        "output_per_million": 0.08,
        "context_window": 128000,
        "tier": "small",
    },
}

DEFAULT_LARGE_MODEL = "llama-3.3-70b-versatile"
DEFAULT_SMALL_MODEL = "llama-3.1-8b-instant"

def get_model_info(model_name: str) -> dict:
    """Return the catalog entry for a model, or a safe default."""
    return MODEL_CATALOG.get(model_name, {
        "provider": "unknown",
        "input_per_million": 0.0,
        "output_per_million": 0.0,
        "context_window": 0,
        "tier": "unknown",
    })

