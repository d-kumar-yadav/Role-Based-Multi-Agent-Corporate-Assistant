from app.rag.retriever import retrieve_documents

def retriever_node(state):
    """
    Calls the Phase 1 retriever (with role filtering).
    """
    query = state.get("query")
    user_role = state.get("user_role")
    
    # Retrieve documents using vector similarity + metadata filter
    docs = retrieve_documents(query, user_role, k=25)
    
    # Combine content for context directly (bypassing the removed reranker)
    context = "\n\n".join([doc.page_content for doc in docs])
    
    return {"context": context, "retrieved_docs_count": len(docs)}
