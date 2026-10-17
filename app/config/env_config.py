import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Required (fail at import if missing)
    MODEL: str = os.environ.get("MODEL", "llama-3.3-70b-versatile")
    FIREWALL_MODEL: str = os.environ.get("FIREWALL_MODEL", "llama-3.1-8b-instant")
    ROUTER_MODEL: str = os.environ.get("ROUTER_MODEL", "llama-3.1-8b-instant")

    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    FIREWALL_GROQ_API_KEY: str = os.environ.get("FIREWALL_GROQ_API_KEY", "")

    JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))

    QDRANT_URL: str | None = os.environ.get("QDRANT_URL") or None
    ENV: str = os.environ.get("ENV", "dev")
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    # Cache
    RESPONSE_CACHE_ENABLED: bool = os.environ.get("RESPONSE_CACHE_ENABLED", "true").lower() == "true"


settings = Settings()

# Module-level aliases for backward compatibility with existing imports
# Module-level aliases for backward compatibility
MODEL = settings.MODEL
FIREWALL_MODEL = settings.FIREWALL_MODEL
ROUTER_MODEL = settings.ROUTER_MODEL

# Validate required vars only when ENV != "test"
if settings.ENV != "test":
    _missing = []
    if not settings.GROQ_API_KEY:
        _missing.append("GROQ_API_KEY")
    if not settings.FIREWALL_GROQ_API_KEY:
        _missing.append("FIREWALL_GROQ_API_KEY")
    if not settings.JWT_SECRET:
        _missing.append("JWT_SECRET")
    if _missing:
        raise RuntimeError(f"Missing required env vars: {_missing}")