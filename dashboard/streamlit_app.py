import os
import uuid
from datetime import datetime

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Meridian Copilot", layout="centered")


def _init_state():
    defaults = {
        "token": None,
        "user": None,
        "thread_id": None,
        "messages": [],
    }
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
            st.error("Token accepted but /auth/me failed.")
            st.session_state.token = None
            return False
    except requests.RequestException as e:
        st.error(f"Cannot fetch profile: {e}")
        st.session_state.token = None
        return False

    return True


def _logout():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.thread_id = None
    st.session_state.messages = []


def _render_login():
    st.title("Meridian Copilot")
    st.caption("Sign in to continue.")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="alice.johnson@meridianglobal.example")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if not email or not password:
            st.warning("Email and password are required.")
        elif _login(email, password):
            st.rerun()

    with st.expander("Demo credentials"):
        st.markdown(
            "- alice.johnson@meridianglobal.example / password123 (employee)\n"
            "- bob.smith@meridianglobal.example / password123 (manager)\n"
            "- meera.iyer@meridianglobal.example / password123 (hr)\n"
            "- vikram.singh@meridianglobal.example / password123 (finance)\n"
            "- suresh.pillai@meridianglobal.example / password123 (it)\n"
            "- cto.executive@meridianglobal.example / password123 (executive)\n"
        )


def _render_sidebar():
    user = st.session_state.user or {}
    st.sidebar.markdown("### Signed in")
    st.sidebar.markdown(f"**{user.get('name', '')}**")
    st.sidebar.caption(f"Role: {user.get('role', '')}")
    st.sidebar.caption(f"Department: {user.get('department', '')}")

    if st.sidebar.button("Sign out", use_container_width=True):
        _logout()
        st.rerun()

    st.sidebar.markdown("---")

    if st.sidebar.button("New chat", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()


def _send_query(query: str) -> dict:
    if not st.session_state.thread_id:
        st.session_state.thread_id = str(uuid.uuid4())

    payload = {
        "query": query,
        "thread_id": st.session_state.thread_id,
    }
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
        return {"status": "error", "response": "Session expired. Please sign in again."}

    if r.status_code != 200:
        return {"status": "error", "response": f"HTTP {r.status_code}"}

    return r.json()


def _render_message(role: str, content: str, meta: dict | None = None):
    with st.chat_message(role):
        st.markdown(content)
        if meta:
            request_id = meta.get("request_id", "")
            status = meta.get("status", "")
            citations = meta.get("citations") or []
            if citations:
                with st.expander(f"Sources ({len(citations)})"):
                    for c in citations:
                        doc_id = c.get("doc_id", "")
                        title = c.get("title", "")
                        version = c.get("version", "")
                        section = c.get("section", "")
                        line = f"**{doc_id}** — {title}"
                        if version:
                            line += f" (v{version})"
                        if section:
                            line += f", {section}"
                        st.markdown(line)
            if request_id:
                st.caption(f"request_id: {request_id} | status: {status}")


def _render_chat():
    st.title("Chat")

    for msg in st.session_state.messages:
        _render_message(msg["role"], msg["content"], msg.get("meta"))

    prompt = st.chat_input("Ask about HR, IT, or Finance policies...")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    _render_message("user", prompt)

    with st.spinner("Thinking..."):
        result = _send_query(prompt)

    response_text = result.get("response") or result.get("final_answer") or ""
    meta = {
        "request_id": result.get("request_id", ""),
        "status": result.get("status", ""),
        "citations": result.get("citations", []),
    }
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "meta": meta,
    })
    _render_message("assistant", response_text, meta)


def _render_audit():
    st.title("Audit log")
    st.caption("Visible to HR and executive roles.")

    user = st.session_state.user or {}
    if user.get("role") not in ("hr", "executive"):
        st.info("Your role does not have access to the audit log.")
        return

    try:
        r = requests.get(f"{API_URL}/metrics", headers=_auth_headers(), timeout=10)
        if r.status_code != 200:
            st.error(f"Metrics unavailable (HTTP {r.status_code}).")
            return
        metrics = r.json()
    except requests.RequestException as e:
        st.error(f"Cannot fetch metrics: {e}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total requests", metrics.get("total_requests", 0))
    col2.metric("Blocked", metrics.get("blocked_count", 0))
    col3.metric("Block rate %", metrics.get("block_rate_pct", 0.0))

    lat = metrics.get("latency_ms", {})
    col4, col5, col6, col7 = st.columns(4)
    col4.metric("Avg latency ms", lat.get("avg", 0))
    col5.metric("p50", lat.get("p50", 0))
    col6.metric("p95", lat.get("p95", 0))
    col7.metric("p99", lat.get("p99", 0))

    cost = metrics.get("cost_usd", {})
    st.markdown(f"**Total cost USD:** {cost.get('total', 0.0)}  ")
    st.markdown(f"**Cost per query USD:** {cost.get('per_query', 0.0)}")

    cache = metrics.get("cache", {})
    if cache:
        st.markdown(f"**Cache entries:** {cache.get('entries', 0)}")


def main():
    _init_state()

    if not st.session_state.token:
        _render_login()
        return

    _render_sidebar()

    user = st.session_state.user or {}
    is_admin = user.get("role") in ("hr", "executive")

    if is_admin:
        tab_chat, tab_audit = st.tabs(["Chat", "Audit"])
        with tab_chat:
            _render_chat()
        with tab_audit:
            _render_audit()
    else:
        _render_chat()


if __name__ == "__main__":
    main()
