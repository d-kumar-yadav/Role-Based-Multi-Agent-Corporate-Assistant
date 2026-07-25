import json
import os
import time

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs", "audit_log.jsonl")

def log_request(user_id: str, role: str, query: str, blocked: bool, block_reason: str, latency: float, final_response: str):
    log_entry = {
        "timestamp": time.time(),
        "user_id": user_id,
        "role": role,
        "query": query,
        "blocked": blocked,
        "block_reason": block_reason,
        "latency_sec": latency,
        "final_response": final_response
    }
    
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
