import os
import logging
import time
import uuid
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.deps import get_current_user
from app.auth.models import User
from app.auth.passwords import verify_password
from app.auth.store import DEMO_PASSWORD_HASH, get_user_by_email
from app.auth.tokens import create_access_token
from app.models.schemas import Citation, QueryRequest, QueryResponse, QueryStatus
from app.guardrails.input_checks import run_input_guardrails
from app.guardrails.output_checks import run_output_guardrails
from app.agents.graph import create_graph
from app.observability.logger import log_request
from app.observability.metrics import record_request, get_metrics
from app.observability.prometheus_export import get_prometheus_metrics
from app.observability.response_cache import get_cached, set_cached, cache_stats
from app.config.env_config import settings

if not hasattr(QueryStatus, "ANSWERED"):
    QueryStatus.ANSWERED = QueryStatus.answered

logger = logging.getLogger("api.main")

_REQUIRED_ENV = ["JWT_SECRET", "GROQ_API_KEY", "FIREWALL_GROQ_API_KEY"]
_missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required env vars: {_missing}")

app = FastAPI(title="Secure Agentic RAG Gateway", version="1.0.0")

# In FastAPI, any code written outside of the @app.post functions runs exactly once when you first turn the server on. Any code written inside the @app.post functions runs every single time a user asks a question.

agent_graph = create_graph()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/auth/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, DEMO_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer"}

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
async def handle_query(
    request: QueryRequest,
    response: Response,
    user: User = Depends(get_current_user),
):
    request_id = uuid.uuid4().hex
    response.headers["X-Request-ID"] = request_id
    start_time = time.time()
    effective_thread_id = f"{user.user_id}:{request.thread_id or 'default'}"

    input_check = run_input_guardrails(request.query)

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
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.answered,
            response=input_check["dialog_response"],
            citations=[],
        )

    if input_check["blocked"]:
        latency = time.time() - start_time
        log_request(
            request_id=request_id,
            user_id=user.user_id,
            role=user.role,
            query=request.query,
            blocked=True,
            reason=input_check.get("reason", "blocked"),
            stage="input_blocked",
            latency_sec=latency,
            final_response="",
            block_stage=input_check.get("stage", ""),
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
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.blocked,
            response="Request blocked by security policies.",
            citations=[],
        )

    # Cache check (only for non-dialog, non-blocked queries)
    cache_enabled = settings.RESPONSE_CACHE_ENABLED
    if cache_enabled:
        cached_response = get_cached(request.query, user.role)
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
            return QueryResponse(
                request_id=request_id,
                status=QueryStatus.ANSWERED,
                response=cached_response,
                citations=[],
            )

    response.headers["X-Cache"] = "MISS"

    state = {
        "query": request.query,
        "user_role": user.role,
        "user_departments": user.allowed_departments,
    }
    try:
        config = {"configurable": {"thread_id": effective_thread_id}}
        result_state = agent_graph.invoke(state, config=config)
        raw_answer = result_state.get("final_answer", "")
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
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.error,
            response=err_msg,
            citations=[],
        )

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
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.blocked,
            response=output_check["final_answer"],
            citations=[],
        )

    final_response = output_check["final_answer"]
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

    if cache_enabled:
        set_cached(request.query, user.role, final_response)

    citations_data = result_state.get("citations", [])
    citations = [Citation(**c) for c in citations_data]
    return QueryResponse(
        request_id=request_id,
        status=QueryStatus.answered,
        response=final_response,
        citations=citations,
    )


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

