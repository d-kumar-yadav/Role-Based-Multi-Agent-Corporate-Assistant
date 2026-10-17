import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("observability.metrics")

LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / ".." / "logs"
LOG_DIR = LOG_DIR.resolve()
DB_PATH = LOG_DIR / "metrics.db"

_lock = threading.Lock()
_conn = None

def _get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT UNIQUE,
                    timestamp_unix REAL NOT NULL,
                    user_id TEXT,
                    role TEXT,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    stage TEXT,
                    latency_ms REAL,
                    tokens_in INTEGER DEFAULT 0,
                    tokens_out INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    retrieved_docs_count INTEGER DEFAULT 0
                )
            """)
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON requests(timestamp_unix)"
            )
            _conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_blocked ON requests(blocked)"
            )
            _conn.commit()
    return _conn

def record_request(
    request_id: str,
    user_id: str,
    role: str,
    blocked: bool,
    stage: str,
    latency_ms: float,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    retrieved_docs_count: int = 0,
) -> None:
    """Insert a metrics row. Uses INSERT OR IGNORE to be idempotent."""
    conn = _get_conn()
    with _lock:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO requests
                  (request_id, timestamp_unix, user_id, role, blocked,
                   stage, latency_ms, tokens_in, tokens_out, cost_usd,
                   retrieved_docs_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    datetime.now(timezone.utc).timestamp(),
                    user_id,
                    role,
                    1 if blocked else 0,
                    stage,
                    latency_ms,
                    tokens_in,
                    tokens_out,
                    cost_usd,
                    retrieved_docs_count,
                ),
            )
            conn.commit()
        except Exception as e:
            logger.warning("Failed to record metric: %s", e)

def _window_to_seconds(window: str) -> float:
    """Convert '1h' / '24h' / '7d' / 'all' to seconds."""
    w = window.strip().lower()
    if w == "all":
        return 0
    unit = w[-1]
    try:
        num = float(w[:-1])
    except ValueError:
        return 86400  # default 24h
    if unit == "m":
        return num * 60
    if unit == "h":
        return num * 3600
    if unit == "d":
        return num * 86400
    return 86400

def get_metrics(window: str = "24h") -> dict:
    """
    Return metrics summary for a time window.
    Computes p50/p95/p99 latency, block rate, cost, etc.
    """
    conn = _get_conn()
    secs = _window_to_seconds(window)
    if secs > 0:
        since = datetime.now(timezone.utc).timestamp() - secs
        where = "WHERE timestamp_unix >= ?"
        params = (since,)
    else:
        where = ""
        params = ()

    with _lock:
        cur = conn.execute(f"SELECT COUNT(*) FROM requests {where}", params)
        total = cur.fetchone()[0]

        cur = conn.execute(
            f"SELECT COUNT(*) FROM requests {where}{' AND' if where else ' WHERE'} blocked = 1",
            params,
        )
        blocked = cur.fetchone()[0]

        cur = conn.execute(
            f"SELECT stage, COUNT(*) FROM requests {where}{' AND' if where else ' WHERE'} blocked = 1 GROUP BY stage",
            params,
        )
        reasons = {row[0] or "unknown": row[1] for row in cur.fetchall()}

        cur = conn.execute(
            f"SELECT latency_ms FROM requests {where} ORDER BY latency_ms",
            params,
        )
        latencies = [row[0] for row in cur.fetchall() if row[0] is not None]

        cur = conn.execute(
            f"SELECT COALESCE(SUM(cost_usd), 0), COALESCE(SUM(tokens_in), 0), COALESCE(SUM(tokens_out), 0) FROM requests {where}",
            params,
        )
        total_cost, tokens_in, tokens_out = cur.fetchone()

        cur = conn.execute(
            f"SELECT COALESCE(AVG(retrieved_docs_count), 0) FROM requests {where}",
            params,
        )
        avg_retrieved = cur.fetchone()[0]

    def pct(sorted_list, p):
        if not sorted_list:
            return 0.0
        idx = max(0, min(len(sorted_list) - 1, int(len(sorted_list) * p)))
        return round(sorted_list[idx], 2)

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    return {
        "window": window,
        "total_requests": total,
        "blocked_count": blocked,
        "block_rate_pct": round(blocked / total * 100, 2) if total else 0.0,
        "block_reasons": reasons,
        "latency_ms": {
            "avg": avg_latency,
            "p50": pct(latencies, 0.50),
            "p95": pct(latencies, 0.95),
            "p99": pct(latencies, 0.99),
        },
        "cost_usd": {
            "total": round(total_cost, 4),
            "per_query": round(total_cost / total, 6) if total else 0.0,
        },
        "tokens": {
            "input": tokens_in,
            "output": tokens_out,
        },
        "avg_retrieved_docs": round(avg_retrieved, 2),
    }
