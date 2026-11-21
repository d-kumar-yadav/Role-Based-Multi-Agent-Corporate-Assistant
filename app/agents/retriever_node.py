from app.rag.retriever import retrieve_documents
from app.guardrails.retrieved_content_sanitizer import sanitize_and_wrap


def retriever_node(state: dict) -> dict:
    query = (state.get("query") or "").strip()
    user_role = state.get("user_role")
    user_departments = state.get("user_departments")
    domains = state.get("domains") or []

    # Fail closed: no identity, no documents
    if not query or not user_role or user_departments is None:
        return {"retrieved_docs": []}

    try:
        result = retrieve_documents(
            query, user_role, user_departments, domains=domains
        )
    except Exception:
        return {"retrieved_docs": []}
    
    docs_list = [
        {
            "doc_id": doc.metadata.get("doc_id", ""),
            "title": doc.metadata.get("title", ""),
            "section": doc.metadata.get("section", ""),
            "version": doc.metadata.get("version", ""),
            "department": doc.metadata.get("department", ""),
            "content": sanitize_and_wrap(doc.metadata.get("doc_id", ""), doc.page_content),
        }
        for doc in result
    ] # converted into list of dict

    return {
        "retrieved_docs": docs_list,
    }
