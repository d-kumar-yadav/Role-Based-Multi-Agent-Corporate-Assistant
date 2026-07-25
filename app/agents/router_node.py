from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

llm = ChatGroq(model=env_config.MODEL, temperature=0)

def router_node(state):
    """
    Classify which document domain the query belongs to (hr, finance, it).
    """
    query = state.get("query")
    
    prompt = PromptTemplate.from_template(
        "You are an intelligent routing agent for a corporate system. Your task is to classify the user's query into exactly one of the following domains:\n"
        "- 'hr': Human resources, employee benefits, leave policies, payroll.\n"
        "- 'finance': Budgets, revenue reports, accounting, and financial compliance.\n"
        "- 'it': Technical support, runbooks, VPN, software access, and hardware issues.\n\n"
        "Instructions:\n"
        "1. Analyze the query carefully.\n"
        "2. Output ONLY the exact word 'hr', 'finance', or 'it'.\n"
        "3. Do not include any punctuation, explanation, or extra text.\n"
        "4. If the query does not clearly match 'finance' or 'it', default to 'hr'.\n\n"
        "Query: {query}\n\n"
        "Category:"
    )
    
    chain = prompt | llm
    response = chain.invoke({"query": query})
    domain = response.content.strip().lower()
    
    if domain not in ["hr", "finance", "it"]:
        domain = "hr"
        
    return {"domain": domain}
