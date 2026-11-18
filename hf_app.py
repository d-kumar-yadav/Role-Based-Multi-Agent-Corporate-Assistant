import os
import sys

# Ensure root directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pre-import torch to avoid Windows DLL conflict with gradio/matplotlib
try:
    import torch
except ImportError:
    pass

# ZeroGPU compatibility for Hugging Face Spaces
try:
    import spaces

    @spaces.GPU
    def _zero_gpu_startup():
        return True

    _zero_gpu_startup()
    print("[Startup] ZeroGPU initialized successfully.")
except Exception:
    pass

import gradio as gr
from app.main import app as fastapi_app
from app.rag.ingest import ingest_documents

# Auto-seed policies into Qdrant if running on a fresh container
try:
    from app.rag.vectorstore import get_vectorstore, COLLECTION_NAME
    vs = get_vectorstore()
    try:
        count = vs.client.count(COLLECTION_NAME).count
    except Exception:
        count = 0
    if count == 0:
        print("[Startup] Seeding initial policy documents into Qdrant...")
        ingest_documents(reset=False)
except Exception as e:
    print(f"[Startup] Notice during vectorstore check: {e}")

# Landing page UI for Hugging Face Space
with gr.Blocks(title="Meridian Copilot AI Gateway", theme=gr.themes.Base()) as demo:
    gr.Markdown("# 🛡️ Meridian Copilot — AI Gateway")
    gr.Markdown("Enterprise AI Gateway with Dynamic RBAC, Dual-Layer Guardrails, and LangGraph Multi-Agent Orchestration.")
    gr.Markdown("---")
    gr.Markdown("### 🟢 Status: Gateway Online & Operational")
    gr.Markdown(
        """
        - **Interactive API Documentation (Swagger):** [/docs](/docs)
        - **System Health:** [/health](/health)
        - **System Telemetry:** [/metrics](/metrics)
        - **Audit Trail:** Active in `logs/audit_log.jsonl`
        """
    )

# Mount Gradio onto the existing FastAPI app
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
