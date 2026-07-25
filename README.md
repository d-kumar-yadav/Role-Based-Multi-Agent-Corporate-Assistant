# Secure Agentic RAG Gateway (AI Firewall) 🛡️

Welcome to the **Secure Agentic RAG Gateway**! This project is a highly secure, enterprise-grade AI assistant designed to handle corporate queries (HR, IT, Finance) while strictly enforcing security policies to prevent data leaks, prompt injections, and off-topic conversations.

## 📖 

Imagine you build an AI chatbot for your company's employees to ask HR, IT, or Finance questions. The problem is: how do you stop an employee from asking the bot to write a poem, generate toxic content, leak sensitive salary data, or hack the bot's instructions?

This project solves that problem. It acts as an **AI Firewall** that sits between the user and the company's knowledge base. 

Whenever a user asks a question, this system evaluates the request through a **Two-Layered Defense System**:
1. **The Bouncer (Native LLM Pre-Check)**: Before doing any heavy lifting, a fast LLM evaluates the user's intent. If the user asks for a recipe, uses toxic language, or tries a "jailbreak" hack, the Bouncer instantly blocks the request with a specific reason.
2. **The Orchestrator (NeMo Guardrails & LangGraph)**: If the query is safe, the Orchestrator steps in. It politely handles basic conversational greetings (e.g., "Hello") or routes complex business questions to specialized Agentic workflows that search the company's internal documents.

By doing this, the system guarantees that the AI remains highly professional, strictly focused on business tasks, and incredibly secure against modern AI vulnerabilities.

---

## ✨ Key Features

* **Two-Layered Input Guardrails**: 
  * A native Llama-3-powered intent checker that categorizes and explicitly blocks violations (Jailbreaks, Off-topic, Competitors, Sensitive data).
  * Nvidia's **NeMo Guardrails** for semantic routing and safe conversational dialog orchestration.
* **Role-Based Access Control (RBAC)**: Ensures users can only query information relevant to their access level (e.g., an IT engineer cannot query secure Finance documents).
* **Agentic RAG with LangGraph**: Intelligently routes approved queries to specific domain agents (HR, Finance, IT) to retrieve correct context and formulate answers.
* **Output Guardrails**: A final security checkpoint that validates the AI's generated response to ensure no hallucinations or sensitive data leaks occur before showing it to the user.
* **Comprehensive Observability**: Logs all interactions, blocked queries, latency, and reasons for blocking, which are viewable on a local dashboard.
* **Fully Dockerized**: Easily deployable anywhere using Docker Compose.

---

## 🖼️ Project Screenshots

Here is a look at the system in action (including the dashboard and query blocking):

![Screenshot 1](assets/Screenshot%202026-07-25%20182600.png)
<br>
![Screenshot 2](assets/Screenshot%202026-07-25%20190828.png)
<br>
![Screenshot 3](assets/Screenshot%202026-07-25%20190902.png)
<br>
![Screenshot 4](assets/Screenshot%202026-07-25%20190950.png)

---

## 🏗️ How It Works (Architecture Overview)

1. **User Request**: A user submits a query via the API (e.g., `"how to make coffee"`).
2. **PII Check**: The system uses pattern matching to ensure no Social Security Numbers or Credit Cards are in the prompt.
3. **Firewall Policy Check (Layer 1)**: The query is passed to a strict Groq-powered LLM with temperature `0.0`. It categorizes the prompt against strict policies. In the coffee example, it flags it as `OFF_TOPIC` and immediately returns a rejection message.
4. **Dialog Check (Layer 2)**: If safe, the query passes to NeMo Guardrails. If the user said "Hello", NeMo Guardrails matches it to a safe greeting flow using vector embeddings (`all-MiniLM-L6-v2`) and replies instantly.
5. **LangGraph Execution**: If it's a business question, it is routed to a specialized AI Agent (HR, IT, Finance) based on the user's role. The agent retrieves relevant documents (RAG) and generates an answer.
6. **Output Guardrails**: The generated answer is validated one last time to ensure it is professional and accurate.
7. **Response**: The user receives the final answer!

---

## 🚀 Getting Started

### Prerequisites
- Docker and Docker Compose
- API Keys for LangSmith, Groq, and Tavily (configured in `.env`)

### Installation & Running

1. Clone the repository.
2. Ensure your `.env` file is populated with your API keys:
   ```env
   GROQ_API_KEY=your_key
   FIREWALL_GROQ_API_KEY=your_key
   LANGSMITH_API_KEY=your_key
   ```
3. Start the application using Docker:
   ```bash
   docker compose up --build
   ```
4. The backend API will be available at `http://localhost:8000` and the Dashboard will be accessible via its configured port.

### Testing the Firewall

You can test the firewall directly using a POST request:

```bash
# Example: This will be explicitly BLOCKED as OFF-TOPIC by the firewall!
Invoke-RestMethod -Uri http://localhost:8000/query -Method Post -ContentType "application/json" -Body '{"query": "how to make coffee", "user_id": "hr", "thread_id": "test_thread"}'
```

---

## 🛠️ Tech Stack

- **FastAPI**: High-performance backend framework.
- **LangChain / LangGraph**: For building the agentic routing and RAG pipelines.
- **NeMo Guardrails**: Nvidia's framework for semantic dialog routing.
- **Groq**: Ultra-fast LLM inference engine used for the Firewall's native checks.
- **Docker**: Containerization for seamless deployment.

---

## 📂 Folder Structure

```text
ai-firewall/
├── app/
│   ├── agents/                   # LangGraph nodes and agent orchestration
│   │   ├── graph.py              # Main router and workflow definition
│   │   ├── hr_agent_node.py      # HR specialized agent
│   │   ├── it_agent_node.py      # IT specialized agent
│   │   ├── finance_agent_node.py # Finance specialized agent
│   │   └── validator_node.py     # Checks agent output before returning
│   ├── auth/                     
│   │   └── roles.py              # RBAC implementation
│   ├── config/                   
│   │   └── env_config.py         # Environment configurations
│   ├── guardrails/               
│   │   ├── input_checks.py       # Layer 1 Native LLM Firewall & PII checker
│   │   ├── output_checks.py      # Final verification of AI responses
│   │   └── nemo_config/          # Layer 2 NeMo Guardrails configuration
│   │       ├── config.yml        # NeMo configuration rules
│   │       ├── rails.co          # Conversational dialog logic
│   │       └── config.py         # Custom LangChain model wrappers
│   ├── rag/                      
│   │   ├── ingest.py             # Ingestion scripts for vector DB
│   │   ├── retriever.py          # Document search logic
│   │   ├── vectorstore.py        # Database connection logic
│   │   ├── qdrant_db/            # Local vector database storage
│   │   └── documents/            # All enterprise PDFs and policies
│   ├── observability/            
│   │   └── logger.py             # Dashbboard and console logging setup
│   └── main.py                   # FastAPI Application Entrypoint
├── assets/                       # UI screenshots for documentation
├── dashboard/                    # Frontend analytics dashboard code
├── logs/                         # Execution logs storage
├── .env                          # API keys and secrets (Git ignored)
├── docker-compose.yml            # Docker multi-container configuration
├── Dockerfile                    # Backend container build instructions
├── requirements.txt              # Python dependencies
└── README.md                     # You are here!
```
