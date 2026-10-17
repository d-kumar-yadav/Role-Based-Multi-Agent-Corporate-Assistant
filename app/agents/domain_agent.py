from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from app.config import env_config

llm = ChatGroq(model=env_config.MODEL, temperature=0)

DOMAIN_PERSONAS = {
    "hr": {
        "persona": "an expert Human Resources Agent",
        "tone": "professional, empathetic, and helpful",
        "refusal": "I don't have access to HR documents for your role.",
    },
    "finance": {
        "persona": "an expert Corporate Finance Agent",
        "tone": "precise, formal, and objective",
        "refusal": "I don't have access to Finance documents for your role.",
    },
    "it": {
        "persona": "an expert IT Support Agent",
        "tone": "clear, technical, and direct",
        "refusal": "I don't have access to IT documents for your role.",
    },
}

PROMPT_TEMPLATE = """You are {persona}. Tone: {tone}.

Instructions:
1. Base your answer STRICTLY on the context below.
2. If the context does not contain the answer, respond with the exact
   phrase: INSUFFICIENT_CONTEXT
3. Cite the doc_id for every factual claim.
4. Do not invent facts, numbers, or policy details.

Context:
{context}

Query: {query}

Answer:"""


def make_domain_agent(domain: str):
    cfg = DOMAIN_PERSONAS[domain]
    prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)
    chain = prompt | llm

    def node(state: dict) -> dict:
        query = state.get("query", "")
        retrieved_docs = state.get("retrieved_docs", [])
        retrieved_count = state.get("retrieved_docs_count", 0)

        if retrieved_count == 0 or not retrieved_docs:
            return {
                "partial_answers": state.get("partial_answers", []) + [
                    {"domain": domain, "answer": cfg["refusal"], "doc_ids": []}
                ]
            }

        context = "\n\n".join(
            f"[{d['doc_id']}] {d['content']}" for d in retrieved_docs
        )
        response = chain.invoke({
            "persona": cfg["persona"],
            "tone": cfg["tone"],
            "context": context,
            "query": query,
        })

        doc_ids = sorted({d["doc_id"] for d in retrieved_docs})
        return {
            "partial_answers": state.get("partial_answers", []) + [
                {"domain": domain, "answer": response.content, "doc_ids": doc_ids}
            ]
        }

    return node

