import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.domain_agent import PROMPT_TEMPLATE, DOMAIN_PERSONAS
from app.rag.retriever import retrieve_documents

docs = retrieve_documents(
    "how many days of casual leave do I get",
    "employee",
    ["sales"],
)

context = "\n\n".join(
    f"[{d.metadata.get('doc_id', '')}] {d.page_content}"
    for d in docs
)

persona = DOMAIN_PERSONAS["hr"]["persona"]
tone = DOMAIN_PERSONAS["hr"]["tone"]

full_prompt = PROMPT_TEMPLATE.format(
    persona=persona,
    tone=tone,
    context=context,
    query="how many days of casual leave do I get",
)

print("=" * 60)
print("FULL PROMPT SENT TO LLM")
print("=" * 60)
print(full_prompt)
print("=" * 60)