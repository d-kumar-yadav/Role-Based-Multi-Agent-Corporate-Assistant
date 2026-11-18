import os
import logging
import time
import uuid
import threading
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.passwords import verify_password, hash_password
from app.auth.store import DEMO_PASSWORD_HASH, get_user_by_email, save_user, get_user_password_hash
from app.auth.tokens import create_access_token
from app.models.schemas import Citation, QueryRequest, QueryResponse, QueryStatus, SignupRequest
from app.guardrails.input_checks import run_input_guardrails
from app.guardrails.output_checks import run_output_guardrails
from app.guardrails.dialog import start_warmup as dialog_warmup
from app.guardrails.groundedness.nli_check import warmup as nli_warmup
from app.rag.reranker import warmup as rerank_warmup
from app.rag.vectorstore import get_vectorstore
from app.agents.graph import create_graph
from app.observability.logger import log_request
from app.observability.metrics import record_request, get_metrics
from app.observability.prometheus_export import get_prometheus_metrics
from app.observability.response_cache import get_cached, set_cached, cache_stats
from app.config.env_config import settings
from app.storage.chat_history_db import get_user_history, save_user_history, append_chat_turn

logger = logging.getLogger("api.main")

_REQUIRED_ENV = ["JWT_SECRET", "GROQ_API_KEY", "FIREWALL_GROQ_API_KEY"]
_missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required env vars: {_missing}")

app = FastAPI(title="Secure Agentic RAG Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Cache"],
)

agent_graph = create_graph()

def _warm_all():
    dialog_warmup()
    get_vectorstore()
    rerank_warmup()
    nli_warmup()

threading.Thread(target=_warm_all, daemon=True).start()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/auth/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    stored_hash = get_user_password_hash(form_data.username) or DEMO_PASSWORD_HASH
    if not user or not verify_password(form_data.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer"}

@app.post("/auth/signup")
def signup(req: SignupRequest):
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already exists")
    
    user_id = f"E{uuid.uuid4().hex[:10]}"
    
    new_user = User(
        user_id=user_id,
        email=req.email,
        name=req.name,
        role=req.role,
        department=req.department,
        manager_id="E2001", # Default mock manager
        allowed_departments=[req.department.lower(), "public"]
    )
    save_user(new_user, hash_password(req.password))
    return {"message": "User created successfully"}

from pydantic import BaseModel as _PydanticBaseModel

class _ResumeRequest(_PydanticBaseModel):
    thread_id: str
    approved: bool

@app.post("/resume")
def resume_action(req: _ResumeRequest, user: User = Depends(get_current_user)):
    status = "approved" if req.approved else "denied"
    return {
        "status": status,
        "response": f"Action was {'approved and executed successfully' if req.approved else 'denied by user'}."
    }

@app.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "department": user.department,
    }

@app.post("/query", response_model=QueryResponse)
def handle_query(
    request: QueryRequest, 
    response: Response,  
    user: User = Depends(get_current_user),
):
    request_id = uuid.uuid4().hex  
    response.headers["X-Request-ID"] = request_id 
    start_time = time.time() 
    effective_thread_id = f"{user.user_id}:{request.thread_id or 'default'}" 

    def _finish(q_status: QueryStatus, resp_text: str, citations_list=None):
        c_objs = citations_list or []
        c_dicts = [c.dict() if hasattr(c, "dict") else c for c in c_objs]
        try:
            append_chat_turn(
                user_id=user.user_id,
                thread_id=request.thread_id or "default",
                user_query=request.query,
                assistant_response=resp_text,
                citations=c_dicts,
                status=q_status.value if hasattr(q_status, "value") else str(q_status),
            )
        except Exception as ex:
            logger.warning("Could not persist turn to sqlite: %s", ex)
        return QueryResponse(
            request_id=request_id,
            status=q_status,
            response=resp_text,
            citations=c_objs,
        )

    input_check = run_input_guardrails(request.query, user.role)
    stage = input_check.get("stage")
    logged_query = "[redacted: pii]" if stage == "pii" else request.query

    # 1. DIALOG CHECK (Greetings / Goodbyes)
    if input_check.get("is_dialog"):
        latency = time.time() - start_time
        log_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            query=request.query,
            blocked=False,
            reason="scripted_dialog",
            stage="dialog",
            latency_sec=latency,
            final_response=input_check["dialog_response"],
        )
        record_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            blocked=False,
            stage="dialog",
            latency_ms=latency * 1000,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            retrieved_docs_count=0,
        )
        return _finish(
            QueryStatus.answered,
            input_check["dialog_response"],
            [],
        )

    # 2. BLOCKED CHECK (Firewall)
    # IMPORTANT: This is dedented to the correct level!
    if input_check["blocked"]:
        latency = time.time() - start_time
        
        # USE THE POLITE MESSAGE FROM THE FIREWALL
        polite_msg = input_check.get("dialog_response") or "I apologize, but I cannot help with that request. I can only assist with HR, IT, and Finance questions."
        
        log_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            query=logged_query,
            blocked=True,
            reason=input_check["reason"],
            stage="input_blocked",
            latency_sec=latency,
            final_response=polite_msg,
            retrieved_docs_count=0,
        )
        record_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            blocked=True,
            stage="input_blocked",
            latency_ms=latency * 1000,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            retrieved_docs_count=0,
        )
        return _finish(
            QueryStatus.blocked,
            polite_msg,
            [],
        )

    # 3. CACHE CHECK
    cache_enabled = settings.RESPONSE_CACHE_ENABLED 
    cache_scope = f"{user.role}|{','.join(sorted(user.allowed_departments or []))}"
    if cache_enabled:
        cached_response = get_cached(request.query, cache_scope) 
        if cached_response is not None:
            latency = time.time() - start_time
            response.headers["X-Cache"] = "HIT"
            log_request(
                request_id=request_id,
                user_id=user.user_id,
                role=user.role,
                query=request.query,
                blocked=False,
                reason="cache_hit",
                stage="cache",
                latency_sec=latency,
                final_response=cached_response,
            )
            record_request(
                request_id=request_id,
                user_id=user.user_id,
                role=user.role,
                blocked=False,
                stage="cache",
                latency_ms=latency * 1000,
                retrieved_docs_count=0,
            )
            return _finish(
                QueryStatus.answered,
                cached_response,
                [],
            )

    response.headers["X-Cache"] = "MISS"

    # 4. LANGGRAPH AGENTS
    state = {
        "query": request.query,
        "turn_id": request_id,
        "user_role": user.role,
        "user_departments": user.allowed_departments,
        "domains": [],
        "retrieved_docs": [],
        "synthesized_doc_ids": [],
        "citations": [],
        "answer": "",
        "final_answer": "",
    }

    try:
        config = {"configurable": {"thread_id": effective_thread_id}}
        result_state = agent_graph.invoke(state, config=config)
        raw_answer = result_state.get("final_answer") or result_state.get("answer", "")
    except Exception:
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "agent_execution_failed request_id=%s error_id=%s",
            request_id, error_id,
        ) 
        latency = time.time() - start_time
        err_msg = f"An internal error occurred. Reference: {error_id}"
        log_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            query=request.query,
            blocked=True,
            reason=f"agent_error:{error_id}",
            stage="graph_error",
            latency_sec=latency,
            final_response=err_msg,
        )
        record_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            blocked=True,
            stage="graph_error",
            latency_ms=latency * 1000,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            retrieved_docs_count=0,
        )
        return _finish(
            QueryStatus.error,
            err_msg,
            [],
        )

    # 5. OUTPUT GUARDRAILS
    retrieved_docs = result_state.get("retrieved_docs", [])
    output_check = run_output_guardrails(raw_answer, retrieved_docs)
    latency = time.time() - start_time
    retrieved_count = len(retrieved_docs)

    if output_check["blocked"]:
        log_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            query=request.query,
            blocked=True,
            reason=output_check["reason"],
            stage="output_blocked",
            latency_sec=latency,
            final_response=output_check["final_answer"],
            retrieved_docs_count=retrieved_count,
        )
        record_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            blocked=True,
            stage="output_blocked",
            latency_ms=latency * 1000,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            retrieved_docs_count=retrieved_count,
        )
        return _finish(
            QueryStatus.blocked,
            output_check["final_answer"],
            [],
        )

    # 6. SUCCESS
    final_response = output_check["final_answer"]

    # Clean up internal codes and formatting before sending to UI
    if "INSUFFICIENT_CONTEXT" in final_response:
        final_response = "I don't have access to the information needed to answer this query, or the information is not in my knowledge base."

    # Fix the fullwidth Unicode brackets 【 】 that the LLM keeps generating
    final_response = final_response.replace("【", "[").replace("】", "]")
    log_request(
        request_id=request_id,
        user_id=user.user_id,
        role=user.role,
        query=request.query,
        blocked=False,
        reason=output_check.get("reason", ""),
        stage="success",
        latency_sec=latency,
        final_response=final_response,
        retrieved_docs_count=retrieved_count,
    )
    record_request(
        request_id=request_id,
        user_id=user.user_id,
        role=user.role,
        blocked=False,
        stage="success",
        latency_ms=latency * 1000,
        tokens_in=0,
        tokens_out=0,
        cost_usd=0.0,
        retrieved_docs_count=retrieved_count,
    )

    citations_data = result_state.get("citations", [])
    citations = [Citation(**c) for c in citations_data]

    if cache_enabled and citations:
        set_cached(request.query, cache_scope, final_response)

    return _finish(
        QueryStatus.answered,
        final_response,
        citations,
    )

@app.get("/chat/history")
def get_chat_history(user: User = Depends(get_current_user)):
    threads = get_user_history(user.user_id)
    return {"threads": threads}

@app.post("/chat/history")
def post_chat_history(data: dict, user: User = Depends(get_current_user)):
    threads = data.get("threads", data)
    save_user_history(user.user_id, threads)
    return {"status": "ok"}

@app.delete("/chat/history/{thread_id}")
def delete_chat_thread(thread_id: str, user: User = Depends(get_current_user)):
    history = get_user_history(user.user_id)
    filtered = [t for t in history if t.get("id") != thread_id]
    save_user_history(user.user_id, filtered)
    return {"status": "ok", "remaining": len(filtered)}

@app.get("/metrics")
def metrics_endpoint(window: str = "24h"):
    data = get_metrics(window=window)
    data["cache"] = cache_stats()
    return data

@app.get("/metrics/prometheus")
def metrics_prometheus():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(get_prometheus_metrics())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)