from app.rag.retriever import retrieve_documents
from app.guardrails.retrieved_content_sanitizer import sanitize_and_wrap


def retriever_node(state: dict) -> dict:
    """
    Retrieve documents with RBAC enforcement.
    Reads: state["query"], state["user_role"], state["user_departments"]
    Returns: {"retrieved_docs": [...], "retrieved_docs_count": int}
    """
    query = state.get("query", "")
    user_role = state.get("user_role", "")
    user_departments = state.get("user_departments", None)

    docs = retrieve_documents(query, user_role, user_departments)

    docs_list = [
        {
            "doc_id": doc.metadata.get("doc_id", ""),
            "title": doc.metadata.get("title", ""),
            "section": doc.metadata.get("section", ""),
            "version": doc.metadata.get("version", ""),
            "content": sanitize_and_wrap(doc.metadata.get("doc_id", ""), doc.page_content),
        }
        for doc in docs
    ]

    return {
        "retrieved_docs": docs_list,
        "retrieved_docs_count": len(docs_list),
    }
