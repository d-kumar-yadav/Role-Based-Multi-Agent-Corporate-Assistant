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
from app.models.schemas import QueryRequest, QueryResponse, QueryStatus
from app.guardrails.input_checks import run_input_guardrails
from app.guardrails.output_checks import run_output_guardrails
from app.agents.graph import create_graph
from app.observability.logger import log_request

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

    input_check = await run_input_guardrails(request.query)

    if input_check.get("is_dialog"):
        latency = time.time() - start_time
        log_request(user.user_id, user.role, request.query, False,
                    "scripted_dialog", latency, input_check["dialog_response"])
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.answered,
            response=input_check["dialog_response"],
            citations=[],
        )

    if input_check["blocked"]:
        latency = time.time() - start_time
        log_request(user.user_id, user.role, request.query, True,
                    input_check.get("reason", "blocked"), latency, "")
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.blocked,
            response="Request blocked by security policies.",
            citations=[],
        )

    state = {
        "query": request.query,
        "user_role": user.role,
        "user_departments": user.allowed_departments,
    }
    try:
        config = {"configurable": {"thread_id": effective_thread_id}}
        result_state = agent_graph.invoke(state, config=config)
        context = result_state.get("context", "")
        raw_answer = result_state.get("final_answer", "")
    except Exception:
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "agent_execution_failed request_id=%s error_id=%s",
            request_id, error_id,
        )
        latency = time.time() - start_time
        log_request(user.user_id, user.role, request.query, True,
                    f"agent_error:{error_id}", latency, "")
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.error,
            response=f"An internal error occurred. Reference: {error_id}",
            citations=[],
        )

    output_check = run_output_guardrails(context, raw_answer)
    latency = time.time() - start_time

    if output_check["blocked"]:
        log_request(user.user_id, user.role, request.query, True,
                    output_check["reason"], latency, output_check["final_answer"])
        return QueryResponse(
            request_id=request_id,
            status=QueryStatus.blocked,
            response=output_check["final_answer"],
            citations=[],
        )

    final_response = output_check["final_answer"]
    log_request(user.user_id, user.role, request.query, False,
                output_check.get("reason", ""), latency, final_response)

    return QueryResponse(
        request_id=request_id,
        status=QueryStatus.answered,
        response=final_response,
        citations=[],
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

