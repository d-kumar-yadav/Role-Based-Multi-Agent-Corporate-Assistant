import json
import os
from .logger import LOG_FILE

def get_metrics():
    if not os.path.exists(LOG_FILE):
        return {"total_requests": 0, "blocked_count": 0, "block_reasons": {}, "avg_latency": 0}
        
    total = 0
    blocked = 0
    latency_sum = 0
    reasons = {}
    
    with open(LOG_FILE, "r") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            total += 1
            latency_sum += entry.get("latency_sec", 0)
            
            if entry.get("blocked"):
                blocked += 1
                reason = entry.get("block_reason", "Unknown")
                reasons[reason] = reasons.get(reason, 0) + 1
                
    avg_latency = latency_sum / total if total > 0 else 0
    
    return {
        "total_requests": total,
        "blocked_count": blocked,
        "block_reasons": reasons,
        "avg_latency": avg_latency
    }
