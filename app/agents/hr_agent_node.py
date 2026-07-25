from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

llm = ChatGroq(model=env_config.MODEL, temperature=0)

def hr_agent_node(state):
    query = state.get("query")
    context = state.get("context")
    retrieved_docs_count = state.get("retrieved_docs_count", 0)
    
    if retrieved_docs_count == 0:
        return {"answer": "I don't have access to HR documents for your role, or no relevant documents were found."}
        
    prompt = PromptTemplate.from_template(
        "You are an expert Human Resources Agent. Your role is to provide precise, empathetic, and accurate answers regarding company policies, benefits, and employee guidelines.\n\n"
        "Instructions:\n"
        "1. Base your answer on the provided policy language in the context. Synthesize the relevant sections to provide a comprehensive answer to the user's question. Do not include outside knowledge.\n"
        "2. If the context does not contain any relevant information to answer the query, explicitly state: 'I cannot answer this based on the retrieved HR documents.'\n"
        "3. Maintain a professional, helpful, and empathetic tone appropriate for HR.\n\n"
        "Context:\n{context}\n\n"
        "Query: {query}\n\n"
        "Answer:"
    )
    
    chain = prompt | llm
    response = chain.invoke({"context": context, "query": query})
    
    return {"answer": response.content}
