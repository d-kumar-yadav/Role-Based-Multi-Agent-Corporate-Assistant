import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.retriever import retrieve_documents

query = "how many days of casual leave do I get"
docs = retrieve_documents(query, "employee", ["sales"])

print(f"Total: {len(docs)} docs\n")

for i, d in enumerate(docs):
    doc_id = d.metadata.get("doc_id", "?")
    section = d.metadata.get("section", "")
    content = d.page_content.replace("\n", " ")[:300]
    print(f"--- Doc {i+1}: {doc_id} | {section}")
    print(content)
    print()