import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path

logger = logging.getLogger("observability.response_cache")

CACHE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "logs"
CACHE_DIR = CACHE_DIR.resolve()
CACHE_FILE = CACHE_DIR / "response_cache.jsonl"

MAX_ENTRIES = 1000
TTL_SECONDS = 3600
PERSONALIZATION_MARKERS = (" my ", " me ", " i ", " mine ", " we ", " our ")

_lock = threading.Lock()
_cache = OrderedDict()  # key -> {"response": str, "timestamp": float}
_initialized = False

def _make_key(query: str, user_role: str) -> str:
    normalized = query.lower().strip()
    payload = f"{normalized}||{user_role}"
    return hashlib.sha256(payload.encode()).hexdigest()

def _has_personalization(query: str) -> bool:
    lowered = " " + query.lower() + " "
    return any(marker in lowered for marker in PERSONALIZATION_MARKERS)

def _load_from_disk():
    if not CACHE_FILE.exists():
        return
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = entry.get("key")
                ts = entry.get("timestamp", 0)
                response = entry.get("response", "")
                if key and time.time() - ts < TTL_SECONDS:
                    _cache[key] = {"response": response, "timestamp": ts}
    except Exception as e:
        logger.warning("Cache load failed: %s", e)

def _init():
    global _initialized
    with _lock:
        if _initialized:
            return
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _load_from_disk()
        _initialized = True

def _evict_if_needed():
    """Evict expired entries and enforce MAX_ENTRIES."""
    now = time.time()
    # Remove expired entries
    expired = [k for k, v in _cache.items() if now - v["timestamp"] > TTL_SECONDS]
    for k in expired:
        del _cache[k]
    # Enforce size limit (LRU: oldest first)
    while len(_cache) > MAX_ENTRIES:
        _cache.popitem(last=False)

def get_cached(query: str, user_role: str) -> str | None:
    """
    Return cached response if present and valid. None otherwise.
    Never caches personalized queries.
    """
    _init()
    if _has_personalization(query):
        return None

    key = _make_key(query, user_role)
    with _lock:
        entry = _cache.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > TTL_SECONDS:
            del _cache[key]
            return None
        # Move to end (most recently used)
        _cache.move_to_end(key)
        return entry["response"]

def set_cached(query: str, user_role: str, response: str) -> None:
    """
    Store a response. Skips personalized queries and empty responses.
    """
    _init()
    if _has_personalization(query):
        return
    if not response or not response.strip():
        return

    key = _make_key(query, user_role)
    now = time.time()
    with _lock:
        _cache[key] = {"response": response, "timestamp": now}
        _cache.move_to_end(key)
        _evict_if_needed()

        # Append to disk for durability
        try:
            with open(CACHE_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "key": key,
                    "response": response,
                    "timestamp": now,
                }) + "\n")
        except Exception as e:
            logger.warning("Cache persist failed: %s", e)

def cache_stats() -> dict:
    """Return current cache size and TTL."""
    _init()
    with _lock:
        return {
            "entries": len(_cache),
            "max_entries": MAX_ENTRIES,
            "ttl_seconds": TTL_SECONDS,
        }

