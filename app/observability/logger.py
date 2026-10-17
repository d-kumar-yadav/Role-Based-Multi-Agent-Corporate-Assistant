import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("observability.audit")

LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "logs"
LOG_DIR = LOG_DIR.resolve()
LOG_FILE = LOG_DIR / "audit_log.jsonl"

_lock = threading.Lock()
_last_hash = "GENESIS"

def _ensure_dir():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def _canonical_json(obj: dict) -> str:
    """Canonical JSON: sorted keys, no extra whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def _compute_hash(entry_without_hash: dict, prev_hash: str) -> str:
    payload = _canonical_json(entry_without_hash) + prev_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _redact_pii(text: str) -> str:
    """Best-effort PII redaction on log fields. Fail-safe."""
    if not text:
        return ""
    try:
        from presidio_anonymizer import AnonymizerEngine
        from presidio_analyzer import AnalyzerEngine
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        entities = ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
                    "US_SSN", "IBAN_CODE", "IP_ADDRESS"]
        results = analyzer.analyze(text=text, entities=entities, language="en")
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
    except Exception as e:
        logger.warning("PII redaction failed, using fallback: %s", e)
        # Fallback: mask any email-like pattern
        import re
        return re.sub(r"\S+@\S+\.\S+", "[EMAIL_REDACTED]", text)

def _load_last_hash() -> str:
    """On startup, read the last entry's hash from the existing log."""
    if not LOG_FILE.exists():
        return "GENESIS"
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            last_line = None
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if last_line:
            entry = json.loads(last_line)
            return entry.get("entry_hash", "GENESIS")
    except Exception as e:
        logger.warning("Could not load last hash, starting fresh: %s", e)
    return "GENESIS"

def _init_hash_chain():
    global _last_hash
    _last_hash = _load_last_hash()

def log_request(
    request_id: str,
    user_id: str,
    role: str,
    query: str,
    blocked: bool,
    reason: str = "",
    stage: str = "",
    latency_sec: float = 0.0,
    final_response: str = "",
    model: str = "",
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    retrieved_doc_ids: list | None = None,
    retrieved_docs_count: int = 0,
    block_stage: str = "",
) -> None:
    """
    Write an audit entry. PII is redacted, entry is hash-chained.
    Uses a lock for thread safety.
    """
    global _last_hash
    _ensure_dir()

    now = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()

    redacted_query = _redact_pii(query)
    redacted_response = _redact_pii(final_response)

    entry = {
        "request_id": request_id,
        "timestamp_unix": now,
        "timestamp_iso": now_iso,
        "user_id": user_id,
        "role": role,
        "query": redacted_query,
        "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
        "blocked": blocked,
        "reason": reason,
        "stage": stage,
        "block_stage": block_stage,
        "latency_ms": round(latency_sec * 1000, 2),
        "final_response": redacted_response,
        "response_hash": hashlib.sha256(final_response.encode()).hexdigest()[:16],
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "retrieved_doc_ids": retrieved_doc_ids or [],
        "retrieved_docs_count": retrieved_docs_count,
    }

    with _lock:
        prev_hash = _last_hash
        entry_hash = _compute_hash(entry, prev_hash)
        entry["prev_hash"] = prev_hash
        entry["entry_hash"] = entry_hash

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        _last_hash = entry_hash

def verify_chain() -> dict:
    """
    Read the whole log and verify the hash chain is intact.
    Returns {"valid": bool, "entries": int, "broken_at": int|None}
    """
    if not LOG_FILE.exists():
        return {"valid": True, "entries": 0, "broken_at": None}

    prev = "GENESIS"
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                return {"valid": False, "entries": i, "broken_at": i}

            stored_prev = entry.get("prev_hash")
            stored_hash = entry.get("entry_hash")

            if stored_prev != prev:
                return {"valid": False, "entries": i + 1, "broken_at": i}

            check = {k: v for k, v in entry.items()
                     if k not in ("entry_hash", "prev_hash")}
            recomputed = _compute_hash(check, stored_prev)

            if recomputed != stored_hash:
                return {"valid": False, "entries": i + 1, "broken_at": i}

            prev = stored_hash

    return {"valid": True, "entries": i + 1 if 'i' in dir() else 0, "broken_at": None}

# Load hash chain on module import
_init_hash_chain()
