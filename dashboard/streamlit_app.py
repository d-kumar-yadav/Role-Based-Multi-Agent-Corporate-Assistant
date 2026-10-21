import os
import json
import sqlite3
import uuid
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

# Reuse the same metrics.db that already exists in your project
_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "metrics.db")
_db_conn = None


def _get_db() -> sqlite3.Connection:
    """Get (or create) the SQLite connection and ensure the chat_history table exists."""
    global _db_conn
    if _db_conn is None:
        _db_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
        _db_conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                user_id   TEXT PRIMARY KEY,
                threads   TEXT NOT NULL,        -- JSON blob of all threads
                updated_at TEXT NOT NULL
            )
        """)
        _db_conn.commit()
    return _db_conn


def _load_history(user_id: str) -> dict:
    """Load saved threads from DB for this user. Returns {} if none found."""
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT threads FROM chat_history WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return {}


def _save_history(user_id: str, threads: dict) -> None:
    """Upsert current threads into the DB for this user."""
    try:
        conn = _get_db()
        conn.execute("""
            INSERT INTO chat_history (user_id, threads, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                threads    = excluded.threads,
                updated_at = excluded.updated_at
        """, (user_id, json.dumps(threads, ensure_ascii=False)))
        conn.commit()
    except Exception:
        pass  # never crash the UI because of a save failure

def _rerun():
    if hasattr(st, "rerun"):  # hasattr= has attribute means does this object has this property/finction or not means here st is object and does this object has attribute rerun or not 
        st.rerun() # it is called when ever page is refresh/reload
    else:
        st.experimental_rerun()  # same it is just  older version  st.rerun

st.set_page_config(
    page_title="Enterprise Copilot", 
    page_icon="◼️", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# Minimal CSS - Adapts to Light & Dark mode natively
st.markdown("""
<style>
    /* Hide default Streamlit menu, footer, and deploy button, but KEEP the sidebar toggle visible */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stDeployButton"] {display: none;}

    /* User Profile Card */
    .user-profile {
        background-color: var(--secondary-background-color);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .user-profile .name { font-weight: 600; font-size: 1.05rem; margin-bottom: 2px; }
    .user-profile .email { font-size: 0.8rem; opacity: 0.7; margin-bottom: 8px; }
    .user-profile .tag { 
        font-size: 0.75rem; 
        background-color: rgba(128, 128, 128, 0.15); 
        display: inline-block; 
        padding: 2px 8px; 
        border-radius: 12px; 
        margin-right: 4px; 
        font-weight: 500; 
    }
    
    /* Make sidebar history buttons look like a list */
    .stButton > button {
        text-align: left;
        justify-content: flex-start;
        border: none;
        background-color: transparent;
    }
    .stButton > button:hover {
        background-color: rgba(128, 128, 128, 0.1);
    }
</style>
""", unsafe_allow_html=True) #unsafe_allow_html=True this tell render this as a raw html
# unsafe_ = "Hey, you are taking responsibility here.
#            If you pass user input into this HTML,
#            a hacker could inject malicious scripts (XSS attack)."

#this function _init_state run on every re run of stramlitt
def _init_state():
    defaults = {
        "token": None, 
        "user": None, 
        "login_email": "alice.johnson@meridianglobal.example",
        "current_thread_id": str(uuid.uuid4()),
        "threads": {} # Stores chat history: {thread_id: {"title": str, "messages": list}}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
# First time app loads:
#   session_state is empty {}
#   → sets ALL defaults  ✅

# User clicks a button (re-run):
#   session_state already has token = "abc123"
#   → "token" already exists → SKIP, don't overwrite ✅
#   → keeps the real token, doesn't reset to None

def _auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _login(email: str, password: str) -> bool:
    try:
        r = requests.post(
            f"{API_URL}/auth/token",
            data={"username": email, "password": password},
            timeout=10,
        )
    except requests.RequestException as e:
        st.error(f"Cannot reach backend: {e}")
        return False

    if r.status_code != 200:
        st.error("Invalid email or password.")
        return False

    st.session_state.token = r.json()["access_token"]  # r.json convert into python dict beacuse json is a text we cannot exess it 

    try:
        me = requests.get(f"{API_URL}/auth/me", headers=_auth_headers(), timeout=10)
        if me.status_code == 200:
            st.session_state.user = me.json()
        else:
            st.error("Authentication failed.")
            st.session_state.token = None
            return False
    except requests.RequestException:
        st.error("Cannot fetch profile.")
        st.session_state.token = None
        return False

    # Load this user's full chat history from database
    user_id = st.session_state.user.get("user_id", "")
    saved_threads = _load_history(user_id)
    if saved_threads:
        st.session_state.threads = saved_threads
        # Resume the last used thread
        st.session_state.current_thread_id = list(saved_threads.keys())[-1]

    return True


def _logout():
    # Save current threads to database before clearing session
    user = st.session_state.get("user") or {}
    user_id = user.get("user_id", "")
    if user_id and st.session_state.get("threads"):
        _save_history(user_id, st.session_state.threads)

    st.session_state.token = None
    st.session_state.user = None
    st.session_state.threads = {}
    st.session_state.current_thread_id = str(uuid.uuid4())


def _render_login():
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    col2 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Sign in")
        st.caption("Access internal HR, IT, and Finance policies.")
        
        email = st.text_input("Email", value=st.session_state.login_email)
        password = st.text_input("Password", value="password123", type="password")
        
        if st.button("Continue", type="primary", use_container_width=True):
            if not email or not password:
                st.warning("Email and password are required.")
            elif _login(email, password):
                _rerun()

        with st.expander("Demo Accounts (Click to auto-fill)"):
            st.caption("All accounts use the password: `password123`")
            
            demo_accounts = {
                "Employee (Alice)": "alice.johnson@meridianglobal.example",
                "Manager (Bob)": "bob.smith@meridianglobal.example",
                "HR (Meera)": "meera.iyer@meridianglobal.example",
                "Finance (Vikram)": "vikram.singh@meridianglobal.example",
                "IT (Suresh)": "suresh.pillai@meridianglobal.example",
                "Executive (CTO)": "cto.executive@meridianglobal.example"
            }
            
            for i, (role_name, role_email) in enumerate(demo_accounts.items()):
                if i % 2 == 0:
                    c1, c2 = st.columns(2)
                target_col = c1 if i % 2 == 0 else c2
                
                if target_col.button(role_name, key=f"btn_{role_name}", use_container_width=True):
                    st.session_state.login_email = role_email
                    _rerun()


def _render_sidebar():
    user = st.session_state.user or {}
    
    # 1. Brand & Profile
    st.sidebar.markdown("### Enterprise Copilot")
    
    role_title = user.get('role', '').title()
    dept = user.get('department', '').title()
    
    st.sidebar.markdown(f"""
    <div class="user-profile">
        <div class="name">{user.get('name', 'User')}</div>
        <div class="email">{user.get('email', '')}</div>
        <span class="tag">{role_title}</span>
        <span class="tag">{dept}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 2. New Chat Button
    if st.sidebar.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.current_thread_id = str(uuid.uuid4())
        _rerun()

    st.sidebar.divider()
    
    # 3. Chat History List
    st.sidebar.caption("Chat History")
    
    # Sort threads by newest first (based on dict insertion order)
    history = list(st.session_state.threads.items())[::-1] 
    
    if not history:
        st.sidebar.caption("*No past conversations*")
        
    for tid, thread_data in history:
        # Highlight the currently active thread visually
        is_active = (tid == st.session_state.current_thread_id)
        prefix = "▶ " if is_active else "💬 "
        title = thread_data.get("title", "New Conversation")
        
        # Truncate long titles
        display_title = (title[:22] + '...') if len(title) > 22 else title
        
        if st.sidebar.button(f"{prefix}{display_title}", key=f"hist_{tid}", use_container_width=True):
            st.session_state.current_thread_id = tid
            _rerun()

    # 4. Sign Out at the very bottom
    st.sidebar.divider()
    if st.sidebar.button("Sign Out", use_container_width=True):
        _logout()
        _rerun()


def _send_query(query: str) -> dict:
    payload = {"query": query, "thread_id": st.session_state.current_thread_id}
    
    try:
        r = requests.post(
            f"{API_URL}/query",
            json=payload,
            headers=_auth_headers(),
            timeout=60,
        )
    except requests.RequestException as e:
        return {"status": "error", "response": f"Backend unreachable: {e}"}

    if r.status_code == 401:
        _logout()
        _rerun()
        return {"status": "error", "response": "Session expired."}

    if r.status_code != 200:
        return {"status": "error", "response": f"System error (HTTP {r.status_code})"}

    return r.json()


def _render_message(role: str, content: str, meta: dict | None = None):
    with st.chat_message(role):
        st.markdown(content)
        if meta:
            citations = meta.get("citations") or []
            if citations:
                with st.expander(f"View {len(citations)} Sources"):
                    for c in citations:
                        doc_id = c.get("doc_id", "")
                        title = c.get("title", "")
                        version = c.get("version", "")
                        section = c.get("section", "")
                        
                        st.markdown(f"`{doc_id}` — {title} (v{version})")
                        if section:
                            st.caption(f"Section: {section}")


def _render_chat():
    st.markdown("### Policy Chat")
    st.caption("Ask questions about company policies. Answers are restricted by your role.")
    st.divider()

    # Ensure current thread exists in state
    if st.session_state.current_thread_id not in st.session_state.threads:
        st.session_state.threads[st.session_state.current_thread_id] = {
            "title": "New Conversation",
            "messages": []
        }

    current_thread = st.session_state.threads[st.session_state.current_thread_id]

    # Render history for this thread
    for msg in current_thread["messages"]:
        _render_message(msg["role"], msg["content"], msg.get("meta"))

    # Input
    prompt = st.chat_input("Ask a question...")
    if not prompt:
        return

    # If this is the first message, set the thread title to the prompt
    if len(current_thread["messages"]) == 0:
        current_thread["title"] = prompt

    # Add user message
    current_thread["messages"].append({"role": "user", "content": prompt})
    _render_message("user", prompt)

    # Fetch response
    with st.spinner("Retrieving policy..."):
        result = _send_query(prompt)

    response_text = result.get("response") or result.get("final_answer") or "No response generated."
    
    meta = {
        "citations": result.get("citations", []),
        "status": result.get("status", ""),
    }
    
    # Add assistant message
    current_thread["messages"].append({
        "role": "assistant",
        "content": response_text,
        "meta": meta,
    })
    _render_message("assistant", response_text, meta)

    # Auto-save history to database after every message
    user_id = (st.session_state.user or {}).get("user_id", "")
    if user_id:
        _save_history(user_id, st.session_state.threads)


def _render_audit():
    st.markdown("### System Audit")
    st.caption("Administrative metrics and logging.")
    
    user = st.session_state.user or {}
    if user.get("role") not in ("hr", "executive"):
        st.info("Access restricted to HR and Executive roles.")
        return

    try:
        r = requests.get(f"{API_URL}/metrics", headers=_auth_headers(), timeout=10)
        if r.status_code != 200:
            st.error("Metrics endpoint unavailable.")
            return
        metrics = r.json()
    except requests.RequestException:
        st.error("Cannot connect to metrics server.")
        return

    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Requests", metrics.get("total_requests", 0))
    col2.metric("Blocked Queries", metrics.get("blocked_count", 0))
    col3.metric("Block Rate", f"{metrics.get('block_rate_pct', 0.0)}%")

    st.markdown("<br>", unsafe_allow_html=True)
    lat = metrics.get("latency_ms", {})
    col4, col5, col6 = st.columns(3)
    col4.metric("Avg Latency", f"{lat.get('avg', 0)} ms")
    col5.metric("p50 Latency", f"{lat.get('p50', 0)} ms")
    col6.metric("p95 Latency", f"{lat.get('p95', 0)} ms")

    st.divider()
    
    cost = metrics.get("cost_usd", {})
    st.markdown(f"**Total API Cost:** ${cost.get('total', 0.0):.4f}")
    st.markdown(f"**Cost Per Query:** ${cost.get('per_query', 0.0):.4f}")


def main():
    _init_state()

    if not st.session_state.token:
        _render_login()
        return

    _render_sidebar()

    user = st.session_state.user or {}
    is_admin = user.get("role") in ("hr", "executive")

    if is_admin:
        tab_chat, tab_audit = st.tabs(["Chat", "Audit Log"])
        with tab_chat:
            _render_chat()
        with tab_audit:
            _render_audit()
    else:
        _render_chat()


if __name__ == "__main__":
    main()