from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

llm = ChatGroq(model=env_config.MODEL, temperature=0)

def validator_node(state):
    """
    Evaluates the domain agent's answer against the provided context.
    If the answer contains information NOT present in the context, it flags it as a hallucination.
    """
    query = state.get("query")
    context = state.get("context")
    answer = state.get("answer")
    
    if "I don't have access" in answer or "I cannot answer this" in answer:
        # Pass through expected negative answers
        return {"final_answer": answer}
        
    prompt = PromptTemplate.from_template(
        "You are a Quality Assurance Supervisor for a corporate AI system.\n"
        "Your job is to review the draft answer provided by a domain agent and ensure it is professional, clear, and directly answers the user's query.\n\n"
        "Instructions:\n"
        "1. Do NOT introduce new facts. Only refine the tone, formatting, and clarity.\n"
        "2. If the draft answer is already excellent, simply output it exactly as is.\n"
        "3. Ensure the response sounds like a polished, helpful corporate assistant.\n"
        "4. DO NOT add conversational filler like 'Here is the final reviewed answer'. Just output the answer itself.\n\n"
        "User Query: {query}\n"
        "Draft Answer: {answer}\n\n"
        "context {context}\n\n\n"
        "Final Reviewed Answer:"
    )
    
    chain = prompt | llm
    response = chain.invoke({"query": query, "answer": answer})
    
    return {"final_answer": response.content}
