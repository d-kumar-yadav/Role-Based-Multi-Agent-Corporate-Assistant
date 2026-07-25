import streamlit as st
import json
import os
import requests
import uuid
import pandas as pd

CHATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "audit_log.jsonl")
API_URL = os.getenv("API_URL", "http://localhost:8000/query")

st.set_page_config(page_title="AI Firewall Chat", layout="wide")

# --- Helper Functions for Chat Persistence ---
def load_chats():
    if os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_chats(chats):
    with open(CHATS_FILE, "w") as f:
        json.dump(chats, f, indent=4)

if "chats" not in st.session_state:
    st.session_state.chats = load_chats()

if "current_thread_id" not in st.session_state:
    st.session_state.current_thread_id = None

# --- SIDEBAR: Role Selection & Thread Management ---
st.sidebar.title("Configuration")
current_user = st.sidebar.selectbox("Select your role:", [
    "HR", 
    "Finance", 
    "IT"
])
user_id = current_user.lower()

st.sidebar.markdown("---")
st.sidebar.subheader("Chat History")

if st.sidebar.button("+ New Chat", use_container_width=True):
    new_thread = str(uuid.uuid4())
    st.session_state.chats[new_thread] = {
        "user_id": user_id,
        "messages": []
    }
    st.session_state.current_thread_id = new_thread
    save_chats(st.session_state.chats)

# Filter threads by current user
user_threads = {k: v for k, v in st.session_state.chats.items() if v.get("user_id") == user_id}

if user_threads:
    for thread_id in reversed(list(user_threads.keys())):
        # Just use a snippet of the first message as the title
        msgs = user_threads[thread_id]["messages"]
        title = msgs[0]["content"][:20] + "..." if msgs else "Empty Chat"
        
        # Highlight current thread
        btn_type = "primary" if thread_id == st.session_state.current_thread_id else "secondary"
        if st.sidebar.button(f"💬 {title}", key=thread_id, use_container_width=True, type=btn_type):
            st.session_state.current_thread_id = thread_id
            st.rerun()
else:
    st.sidebar.info("No chat history for this user.")

# --- OBSERVABILITY TOGGLE ---
st.sidebar.markdown("---")
show_observability = st.sidebar.checkbox("Show Observability Dashboard", value=False)

# --- MAIN UI: Chat or Observability ---
if show_observability:
    st.title("🛡️ AI Firewall Observability")
    if not os.path.exists(LOG_FILE):
        st.warning("No audit logs found.")
    else:
        logs = []
        with open(LOG_FILE, "r") as f:
            for line in f:
                if line.strip(): logs.append(json.loads(line))
        if logs:
            df = pd.DataFrame(logs)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            st.dataframe(df.sort_values('timestamp', ascending=False).head(50))
            if len(df[df['blocked'] == True]) > 0:
                st.bar_chart(df[df['blocked'] == True]['block_reason'].value_counts())
            else:
                st.success("No requests have been blocked!")
else:
    st.title(f"Enterprise AI Assistant ({user_id})")
    
    # Require switching to a thread that actually belongs to the user
    if st.session_state.current_thread_id and st.session_state.chats.get(st.session_state.current_thread_id, {}).get("user_id") != user_id:
        st.session_state.current_thread_id = None
        
    if not st.session_state.current_thread_id:
        st.info("👈 Please click '+ New Chat' to start.")
    else:
        thread_id = st.session_state.current_thread_id
        chat_data = st.session_state.chats[thread_id]
        
        # Display messages
        for msg in chat_data["messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Chat Input
        if prompt := st.chat_input("Ask a question..."):
            # Add user message to UI immediately
            with st.chat_message("user"):
                st.markdown(prompt)
            chat_data["messages"].append({"role": "user", "content": prompt})
            save_chats(st.session_state.chats)
            
            # Call API
            with st.spinner("Analyzing with AI Firewall..."):
                payload = {
                    "user_id": user_id, 
                    "query": prompt,
                    "thread_id": thread_id
                }
                try:
                    response = requests.post(API_URL, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        bot_response = data["response"]
                        if data["blocked"]:
                            bot_response = f"**🚫 BLOCKED:** {data['reason']}\n\n{bot_response}"
                            
                        with st.chat_message("assistant"):
                            st.markdown(bot_response)
                        chat_data["messages"].append({"role": "assistant", "content": bot_response})
                        save_chats(st.session_state.chats)
                    else:
                        st.error(f"API Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Connection Error: {e} - Is the FastAPI server running?")
