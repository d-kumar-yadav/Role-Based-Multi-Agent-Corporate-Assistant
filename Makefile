.PHONY: help ingest ingest-incremental test run-backend run-frontend eval clean-logs

help:
	@echo "Meridian Copilot - common commands"
	@echo ""
	@echo "  make ingest              Full re-ingest of policies into Qdrant"
	@echo "  make test                Run the full test suite"
	@echo "  make run-backend         Start FastAPI (uvicorn) on port 8000"
	@echo "  make run-frontend        Start Streamlit on port 8501"
	@echo "  make eval                Run the evaluation harness (backend must be running)"
	@echo "  make clean-logs          Delete audit log, metrics DB, response cache"

ingest:
	python -m app.rag.ingest --reset

test:
	pytest tests/ -v

run-backend:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	streamlit run dashboard/streamlit_app.py --server.port 8501

eval:
	python -m app.evaluation.run_eval --url http://localhost:8000

clean-logs:
	rm -f logs/audit_log.jsonl logs/metrics.db logs/response_cache.jsonl

