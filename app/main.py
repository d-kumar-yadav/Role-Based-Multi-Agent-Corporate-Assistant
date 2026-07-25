from fastapi import FastAPI
import uvicorn
import time
from app.models.schemas import QueryRequest, QueryResponse
from app.auth.roles import get_user_role
from app.guardrails.input_checks import run_input_guardrails
from app.guardrails.output_checks import run_output_guardrails
from app.agents.graph import create_graph
from app.observability.logger import log_request

app = FastAPI(title="Secure Agentic RAG Gateway", version="1.0.0")

# In FastAPI, any code written outside of the @app.post functions runs exactly once when you first turn the server on. Any code written inside the @app.post functions runs every single time a user asks a question.

agent_graph = create_graph()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
def handle_query(request: QueryRequest):
    start_time = time.time()
    user_role = get_user_role(request.user_id)
    
    # 1. Input Guardrails
    input_check = run_input_guardrails(request.query)
    
    # Handle safe, scripted dialog (e.g., greetings, goodbyes) to avoid unnecessary processing
    if input_check.get("is_dialog"):
        latency = time.time() - start_time
        log_request(request.user_id, user_role, request.query, False, "Scripted Dialog", latency, input_check["dialog_response"])
        return QueryResponse(response=input_check["dialog_response"], blocked=False, latency_sec=latency)
        
    if input_check["blocked"]:
        latency = time.time() - start_time
        log_request(request.user_id, user_role, request.query, True, input_check["reason"], latency, "")
        return QueryResponse(response="Request blocked by security policies.", blocked=True, reason=input_check["reason"], latency_sec=latency)
        
    # 2. Agent Orchestration (Router -> Retriever -> Domain Agent -> Validator)
    state = {"query": request.query, "user_role": user_role}
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        result_state = agent_graph.invoke(state, config=config)
        context = result_state.get("context", "")
        raw_answer = result_state.get("final_answer", "")
    except Exception as e:
        latency = time.time() - start_time
        err_msg = f"Agent execution failed: {str(e)}"
        log_request(request.user_id, user_role, request.query, True, err_msg, latency, "")
        return QueryResponse(response="Internal System Error", blocked=True, reason=err_msg, latency_sec=latency)
        
    # 3. Output Guardrails
    output_check = run_output_guardrails(context, raw_answer)
    latency = time.time() - start_time
    
    if output_check["blocked"]:
        log_request(request.user_id, user_role, request.query, True, output_check["reason"], latency, output_check["final_answer"])
        return QueryResponse(response=output_check["final_answer"], blocked=True, reason=output_check["reason"], latency_sec=latency)
        
    # 4. Final Safe Response
    final_response = output_check["final_answer"]
    log_request(request.user_id, user_role, request.query, False, output_check.get("reason", ""), latency, final_response)
    
    return QueryResponse(response=final_response, blocked=False, latency_sec=latency)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
