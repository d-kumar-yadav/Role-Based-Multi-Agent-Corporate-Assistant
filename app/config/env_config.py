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
    
    
    
    # "env_config.py is a central config class that reads all environment variables from .env in one place, converts them to the right types (string → bool/int), sets safe defaults, and validates required secrets at startup. Every other file just imports settings and uses settings.GROQ_API_KEY etc. — clean, no duplication, and if a secret is missing, the app fails fast at startup instead of crashing mid-request.
    
    # Why not just use the .env file directly everywhere?

# You could do this in every file:

# python
# # ❌ BAD — doing it everywhere directly
# import os
# # In main.py
# cache = os.environ.get("RESPONSE_CACHE_ENABLED", "true").lower() == "true"
# # In some_other_file.py
# cache = os.environ.get("RESPONSE_CACHE_ENABLED", "true").lower() == "true"
# # In another_file.py
# cache = os.environ.get("RESPONSE_CACHE_ENABLED", "true").lower() == "true"

# Problem: You've written the same thing 50 times across 50 files. If you rename the variable → you have to fix 50 places. If you change the default → fix 50 places.

# What env_config.py solves — One place for everything
# python
# # ✅ GOOD — defined ONCE in env_config.py
# class Settings:
#     RESPONSE_CACHE_ENABLED: bool = os.environ.get("RESPONSE_CACHE_ENABLED", "true").lower() == "true"
#     GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
#     JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
#     # ... all settings in one place
# settings = Settings()
# python
# # Every other file just does:
# from app.config.env_config import settings
# cache = settings.RESPONSE_CACHE_ENABLED  # clean, simple, one line
# key   = settings.GROQ_API_KEY