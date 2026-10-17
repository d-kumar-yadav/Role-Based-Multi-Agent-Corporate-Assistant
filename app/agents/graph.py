import operator
import os
import sqlite3
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from .router_node import router_node
from .retriever_node import retriever_node
from .hr_agent_node import hr_agent_node
from .finance_agent_node import finance_agent_node
from .it_agent_node import it_agent_node
from .synthesizer_node import synthesizer_node
from .validator_node import validator_node


class AgentState(TypedDict):
    query: str
    user_role: str
    user_departments: list[str]
    domains: list[str]
    domain: str
    context: str
    retrieved_docs: list[dict]
    retrieved_docs_count: int
    partial_answers: Annotated[list[dict], operator.add]
    synthesized_doc_ids: list[str]
    citations: list[dict]
    answer: str
    final_answer: str


def route_to_agents(state):
    domains = state.get("domains", ["hr"])
    return [f"{d}_agent" for d in domains]


def create_graph():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("hr_agent", hr_agent_node)
    workflow.add_node("finance_agent", finance_agent_node)
    workflow.add_node("it_agent", it_agent_node)
    workflow.add_node("synthesizer", synthesizer_node)
    workflow.add_node("validator", validator_node)

    # Add edges
    workflow.set_entry_point("router")
    workflow.add_edge("router", "retriever")

    # Conditional edge from retriever to agent(s) based on domains
    workflow.add_conditional_edges(
        "retriever",
        route_to_agents,
        {
            "hr_agent": "hr_agent",
            "finance_agent": "finance_agent",
            "it_agent": "it_agent",
        },
    )

    # Edges from agents to synthesizer
    workflow.add_edge("hr_agent", "synthesizer")
    workflow.add_edge("finance_agent", "synthesizer")
    workflow.add_edge("it_agent", "synthesizer")

    workflow.add_edge("synthesizer", "validator")
    workflow.add_edge("validator", END)

    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "long_term_memory.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    memory = SqliteSaver(conn)

    return workflow.compile(checkpointer=memory)
