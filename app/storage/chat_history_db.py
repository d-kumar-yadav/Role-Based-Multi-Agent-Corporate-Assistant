import os
import json
import sqlite3
import threading
from datetime import datetime

_lock = threading.Lock()

# logs/chat_history.db path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DB_PATH = os.path.join(_PROJECT_ROOT, "logs", "chat_history.db")


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            user_id   TEXT PRIMARY KEY,
            threads   TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get_user_history(user_id: str) -> list[dict]:
    """Retrieve all chat threads for a user from SQLite, normalized as a list of threads."""
    if not user_id:
        return []
    with _lock:
        try:
            conn = _get_connection()
            row = conn.execute(
                "SELECT threads FROM chat_history WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if not row or not row[0]:
                return []
            raw = json.loads(row[0])
            threads_list = []
            if isinstance(raw, dict):
                for tid, tdata in raw.items():
                    if isinstance(tdata, dict):
                        threads_list.append(
                            {
                                "id": tid,
                                "title": tdata.get("title") or "Conversation",
                                "messages": tdata.get("messages") or [],
                            }
                        )
            elif isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict) and "id" in item:
                        threads_list.append(item)
            return threads_list
        except Exception as e:
            print(f"[chat_history_db] Error reading history for {user_id}: {e}")
            return []


def get_recent_thread_messages(user_id: str, thread_id: str, max_messages: int = 6) -> list[dict]:
    """Retrieve the most recent messages for a specific thread of a user."""
    if not user_id or not thread_id:
        return []
    threads = get_user_history(user_id)
    for t in threads:
        if t.get("id") == thread_id:
            msgs = t.get("messages", [])
            return msgs[-max_messages:] if len(msgs) > max_messages else list(msgs)
    return []


def save_user_history(user_id: str, threads: list | dict) -> None:
    """Save/upsert the entire threads collection for a user in SQLite."""
    if not user_id:
        return
    with _lock:
        try:
            conn = _get_connection()
            # Normalize to dict format for backwards compatibility with existing rows
            threads_dict = {}
            if isinstance(threads, list):
                for t in threads:
                    if isinstance(t, dict):
                        tid = t.get("id")
                        if tid:
                            threads_dict[tid] = {
                                "title": t.get("title", "Conversation"),
                                "messages": t.get("messages", []),
                            }
            elif isinstance(threads, dict):
                threads_dict = threads

            threads_json = json.dumps(threads_dict, ensure_ascii=False)
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                """
                INSERT INTO chat_history (user_id, threads, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    threads = excluded.threads,
                    updated_at = excluded.updated_at
                """,
                (user_id, threads_json, now),
            )
            conn.commit()
        except Exception as e:
            print(f"[chat_history_db] Error saving history for {user_id}: {e}")


def append_chat_turn(
    user_id: str,
    thread_id: str,
    user_query: str,
    assistant_response: str,
    citations: list = None,
    status: str = "answered",
) -> None:
    """Directly append a turn (user prompt + assistant response) to a user thread in SQLite."""
    if not user_id or not thread_id:
        return
    with _lock:
        try:
            conn = _get_connection()
            row = conn.execute(
                "SELECT threads FROM chat_history WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            threads_dict = {}
            if row and row[0]:
                raw = json.loads(row[0])
                if isinstance(raw, dict):
                    threads_dict = raw
                elif isinstance(raw, list):
                    for item in raw:
                        if isinstance(item, dict) and "id" in item:
                            threads_dict[item["id"]] = {
                                "title": item.get("title", "Conversation"),
                                "messages": item.get("messages", []),
                            }

            if thread_id not in threads_dict:
                title = user_query.strip()[:36] + ("…" if len(user_query.strip()) > 36 else "")
                threads_dict[thread_id] = {
                    "title": title or "New Conversation",
                    "messages": [],
                }
            elif not threads_dict[thread_id].get("title") or threads_dict[thread_id]["title"] == "New conversation":
                title = user_query.strip()[:36] + ("…" if len(user_query.strip()) > 36 else "")
                threads_dict[thread_id]["title"] = title

            target_thread = threads_dict[thread_id]
            messages = target_thread.setdefault("messages", [])

            # Check if user message already present as last turn to avoid duplicating
            if not (messages and messages[-1].get("role") == "user" and messages[-1].get("content") == user_query):
                messages.append({"role": "user", "content": user_query})

            # Append assistant message
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_response,
                    "meta": {
                        "citations": citations or [],
                        "status": status,
                    },
                }
            )

            threads_json = json.dumps(threads_dict, ensure_ascii=False)
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                """
                INSERT INTO chat_history (user_id, threads, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    threads = excluded.threads,
                    updated_at = excluded.updated_at
                """,
                (user_id, threads_json, now),
            )
            conn.commit()
        except Exception as e:
            print(f"[chat_history_db] Error appending turn for {user_id}: {e}")
