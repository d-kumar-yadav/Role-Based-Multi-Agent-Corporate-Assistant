from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class QueryStatus(str, Enum):
    answered = "answered"
    refused = "refused"
    blocked = "blocked"
    error = "error"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    version: str
    section: str | None = None


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    thread_id: str | None = None


class QueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    status: QueryStatus
    response: str
    citations: list[Citation] = []
