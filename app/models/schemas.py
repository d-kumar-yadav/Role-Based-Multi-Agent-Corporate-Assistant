from pydantic import BaseModel

class QueryRequest(BaseModel):
    user_id: str
    query: str
    thread_id: str = "default_thread"

class QueryResponse(BaseModel):
    response: str
    blocked: bool
    reason: str = None
    latency_sec: float = None
