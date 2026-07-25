from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config


llm = ChatGroq(model=env_config.MODEL, temperature=0)

def finance_agent_node(state):
    query = state.get("query")
    context = state.get("context")
    retrieved_docs_count = state.get("retrieved_docs_count", 0)
    
    if retrieved_docs_count == 0:
        return {"answer": "I don't have access to Finance documents for your role, or no relevant documents were found."}
        
    prompt = PromptTemplate.from_template(
        "You are an expert Corporate Finance Agent. Your role is to provide precise, professional, and accurate answers regarding financial figures, budgets, and compliance.\n\n"
        "Instructions:\n"
        "1. Base your answer STRICTLY on the provided context. Do not include outside knowledge.\n"
        "2. If the context does not contain the answer, explicitly state: 'I cannot answer this based on the retrieved finance documents.'\n"
        "3. Highlight key financial figures and metrics clearly.\n"
        "4. Maintain a formal and objective tone.\n\n"
        "Context:\n{context}\n\n"
        "Query: {query}\n\n"
        "Answer:"
    )
    
    chain = prompt | llm
    response = chain.invoke({"context": context, "query": query})
    
    return {"answer": response.content}
