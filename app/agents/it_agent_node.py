from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

llm = ChatGroq(model=env_config.MODEL, temperature=0)

def it_agent_node(state):
    query = state.get("query")
    context = state.get("context")
    retrieved_docs_count = state.get("retrieved_docs_count", 0)
    
    if retrieved_docs_count == 0:
        return {"answer": "I don't have access to IT documents for your role, or no relevant documents were found."}
        
    prompt = PromptTemplate.from_template(
        "You are an expert IT Support Agent. Your role is to provide clear, technical, and runbook-style answers based strictly on the provided context.\n\n"
        "Instructions:\n"
        "1. Base your answer STRICTLY on the provided context. Do not include outside knowledge or generic troubleshooting steps.\n"
        "2. If the context does not contain the answer, explicitly state: 'I cannot answer this based on the retrieved IT documents.'\n"
        "3. Format technical steps, commands, or system paths clearly using code blocks or bullet points.\n"
        "4. Be concise and direct, simulating a technical runbook response.\n\n"
        "Context:\n{context}\n\n"
        "Query: {query}\n\n"
        "Answer:"
    )
    
    chain = prompt | llm
    response = chain.invoke({"context": context, "query": query})
    
    return {"answer": response.content}
