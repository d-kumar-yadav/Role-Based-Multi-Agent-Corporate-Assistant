import os
import uuid
import streamlit as st
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000")

# 1. Page Config
st.set_page_config(
    page_title="Enterprise Copilot", 
    page_icon="◼️", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# 2. Custom CSS for Minimal, Enterprise UI
st.markdown("""
<style>
    /* Hide default Streamlit menus and footers */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Typography */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #111827;
    }

    /* Background */
    .stApp {
        background-color: #F9FAFB;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E5E7EB;
    }

    /* Buttons */
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        border: 1px solid #D1D5DB;
        background-color: #FFFFFF;
        color: #374151;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        border-color: #9CA3AF;
        background-color: #F3F4F6;
        color: #111827;
    }

    /* Chat Input */
    [data-testid="stChatInput"] {
        border-radius: 8px;
        border: 1px solid #D1D5DB;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }

    /* Expander (Sources) */
    .streamlit-expanderHeader {
        font-size: 0.85rem;
        color: #6B7280;
        font-weight: 500;
    }
    
    /* Metrics in Audit */
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        color: #111827;
    }
    [data-testid="stMetricLabel"] {
        color: #6B7280;
    }
</style>
""", unsafe_allow_html=True)


def _init_state():
    defaults = {"token": None, "user": None, "thread_id": None, "messages": []}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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

    st.session_state.token = r.json()["access_token"]

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

    return True


def _logout():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.thread_id = None
    st.session_state.messages = []


def _render_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Sign in")
        st.caption("Access internal HR, IT, and Finance policies.")
        
        with st.form("login_form"):
            # Pre-filled with demo credentials for easy testing
            email = st.text_input("Email", value="alice.johnson@meridianglobal.example")
            password = st.text_input("Password", value="password123", type="password")
            submitted = st.form_submit_button("Continue")

        if submitted:
            if not email or not password:
                st.warning("Email and password are required.")
            elif _login(email, password):
                st.rerun()

        with st.expander("Demo Accounts"):
            st.markdown(
                "- **Employee:** alice.johnson@meridianglobal.example\n"
                "- **Manager:** bob.smith@meridianglobal.example\n"
                "- **HR:** meera.iyer@meridianglobal.example\n"
                "- **Finance:** vikram.singh@meridianglobal.example\n"
                "- **IT:** suresh.pillai@meridianglobal.example\n"
                "- **Executive:** cto.executive@meridianglobal.example\n\n"
                "*(Password for all accounts: `password123`)*"
            )


def _render_sidebar():
    user = st.session_state.user or {}
    
    st.sidebar.markdown("### Enterprise Copilot")
    st.sidebar.caption("Internal Policy Assistant")
    st.sidebar.markdown("---")
    
    st.sidebar.markdown(f"**{user.get('name', 'User')}**")
    st.sidebar.caption(f"{user.get('role', '').title()} · {user.get('department', '').title()}")
    
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    
    if st.sidebar.button("New Session"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.sidebar.markdown("---")
    
    if st.sidebar.button("Sign Out"):
        _logout()
        st.rerun()


def _send_query(query: str) -> dict:
    if not st.session_state.thread_id:
        st.session_state.thread_id = str(uuid.uuid4())

    payload = {"query": query, "thread_id": st.session_state.thread_id}
    
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
        st.rerun()
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
                        
                        # Minimal citation format
                        st.markdown(f"`{doc_id}` — {title} (v{version})")
                        if section:
                            st.caption(f"Section: {section}")
            else:
                # If no citations, just show a subtle caption
                pass


def _render_chat():
    st.markdown("### Policy Chat")
    st.caption("Ask questions about company policies. Answers are restricted by your role.")
    st.markdown("<hr style='margin-top: 0; margin-bottom: 20px; border-color: #E5E7EB;'>", unsafe_allow_html=True)

    # Render existing chat
    for msg in st.session_state.messages:
        _render_message(msg["role"], msg["content"], msg.get("meta"))

    # Input
    prompt = st.chat_input("Ask a question...")
    if not prompt:
        return

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
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
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "meta": meta,
    })
    _render_message("assistant", response_text, meta)


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

    # Clean Metrics Layout
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

    st.markdown("<br><hr style='border-color: #E5E7EB;'><br>", unsafe_allow_html=True)
    
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