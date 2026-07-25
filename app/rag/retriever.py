from qdrant_client.http import models
from .vectorstore import get_vectorstore

def retrieve_documents(query: str, user_role: str, k: int = 20):
    """
    Retrieve documents based on vector similarity, but strictly filter
    by the user's role before they even reach the LLM.
    """
    vectorstore = get_vectorstore()
    
    # Access control filter: match chunks where metadata role == user_role OR "public"
    # Using Qdrant's native Filter syntax
    search_kwargs = {
        "k": k,
        "filter": models.Filter(
            should=[
                models.FieldCondition(key="metadata.role", match=models.MatchValue(value=user_role)),
                models.FieldCondition(key="metadata.role", match=models.MatchValue(value="public"))
            ]
        )
    }
    
    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    docs = retriever.invoke(query)
    return docs
