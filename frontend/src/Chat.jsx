import { useState, useRef, useEffect, useCallback } from 'react';
import {
  ArrowUp,
  LogOut,
  Plus,
  MessageSquare,
  ShieldAlert,
  Loader2,
  Menu,
  X,
  Trash2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/* ─── helpers ─────────────────────────────────────────────────────────────── */
const uid = () => crypto.randomUUID();

const withCitations = (text) =>
  text.replace(/\(([A-Z]+(?:-[A-Z0-9]+)+)\)/g, ' `$1`');

const initials = (name) =>
  (name || '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join('') || '·';

function getUserIdFromToken(token) {
  try {
    if (!token) return 'anonymous';
    const base64Url = token.split('.')[1];
    if (!base64Url) return 'anonymous';
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    const parsed = JSON.parse(jsonPayload);
    return parsed.sub || parsed.email || 'anonymous';
  } catch (_) {
    return 'anonymous';
  }
}

const getStorageKey = (userId) => `meridian_chat_history_${userId}`;

function loadLocalHistory(userId) {
  try {
    const raw = localStorage.getItem(getStorageKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (_) {}
  const id = uid();
  return [{ id, title: 'New conversation', messages: [], loadingIds: [] }];
}

function saveLocalHistory(userId, history) {
  try {
    const clean = history.map(({ loadingIds: _, ...rest }) => rest);
    localStorage.setItem(getStorageKey(userId), JSON.stringify(clean));
  } catch (_) {}
}

/* ─── component ───────────────────────────────────────────────────────────── */
export default function Chat({ token, onLogout }) {
  const userId = getUserIdFromToken(token);

  // ── CORE STATE ──────────────────────────────────────────────────────────
  const [history, setHistory] = useState(() => loadLocalHistory(userId));
  const [activeId, setActiveId] = useState(() => history[0]?.id);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [input, setInput] = useState('');
  const [userProfile, setUserProfile] = useState(null);
  const bottomRef = useRef(null);

  // Derived: messages & state for the ACTIVE thread
  const activeThread = history.find((h) => h.id === activeId) || history[0];
  const messages = activeThread?.messages || [];
  const isActiveLoading = (activeThread?.loadingIds || []).length > 0;
  const pendingTool =
    messages.findLast?.((m) => m.role === 'system' && m.awaitingApproval) || null;

  // ── PERSIST LOCAL STORAGE ───────────────────────────────────────────────
  useEffect(() => {
    saveLocalHistory(userId, history);
  }, [userId, history]);

  // ── SCROLL ───────────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isActiveLoading]);

  // ── INITIAL DATA: USER PROFILE + SQLITE CHAT HISTORY ─────────────────────
  useEffect(() => {
    if (!token) return;

    // 1. Fetch user profile
    fetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => {
        if (r.status === 401) {
          onLogout();
          return null;
        }
        return r.json();
      })
      .then((d) => {
        if (d) setUserProfile(d);
      })
      .catch(console.error);

    // 2. Fetch SQLite chat history from backend
    fetch(`${API_BASE}/chat/history`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.threads) && data.threads.length > 0) {
          setHistory(data.threads);
          // Set active thread to the first (most recent) thread
          setActiveId(data.threads[0].id);
        }
      })
      .catch(console.error);
  }, [token, onLogout]);

  // ── THREAD HELPERS ───────────────────────────────────────────────────────
  const updateThread = useCallback((tid, updater) => {
    setHistory((prev) => prev.map((h) => (h.id === tid ? updater(h) : h)));
  }, []);

  const appendMsg = useCallback(
    (tid, msg) => {
      updateThread(tid, (h) => ({ ...h, messages: [...h.messages, msg] }));
    },
    [updateThread]
  );

  const addLoading = useCallback(
    (tid, reqId) => {
      updateThread(tid, (h) => ({
        ...h,
        loadingIds: [...(h.loadingIds || []), reqId],
      }));
    },
    [updateThread]
  );

  const removeLoading = useCallback(
    (tid, reqId) => {
      updateThread(tid, (h) => ({
        ...h,
        loadingIds: (h.loadingIds || []).filter((x) => x !== reqId),
      }));
    },
    [updateThread]
  );

  // Sync updated threads list to SQLite backend
  const syncToBackend = useCallback(
    (updatedThreads) => {
      if (!token) return;
      fetch(`${API_BASE}/chat/history`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          threads: updatedThreads.map(({ loadingIds: _, ...rest }) => rest),
        }),
      }).catch(console.error);
    },
    [token]
  );

  // ── NEW CHAT ─────────────────────────────────────────────────────────────
  const handleNewChat = () => {
    const newId = uid();
    const newThread = {
      id: newId,
      title: 'New conversation',
      messages: [],
      loadingIds: [],
    };
    setHistory((prev) => {
      const updated = [newThread, ...prev];
      syncToBackend(updated);
      return updated;
    });
    setActiveId(newId);
    setInput('');
    setSidebarOpen(false);
  };

  // ── SELECT THREAD ────────────────────────────────────────────────────────
  const handleSelectThread = (item) => {
    setActiveId(item.id);
    setInput('');
    setSidebarOpen(false);
  };

  // ── DELETE THREAD ────────────────────────────────────────────────────────
  const handleDeleteThread = (e, threadId) => {
    e.stopPropagation();
    const filtered = history.filter((h) => h.id !== threadId);
    if (filtered.length === 0) {
      const newId = uid();
      filtered.push({
        id: newId,
        title: 'New conversation',
        messages: [],
        loadingIds: [],
      });
    }
    setHistory(filtered);
    if (activeId === threadId) {
      setActiveId(filtered[0].id);
    }

    // Delete in SQLite backend
    fetch(`${API_BASE}/chat/history/${threadId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    }).catch(console.error);
  };

  // ── SEND QUERY ───────────────────────────────────────────────────────────
  const sendQuery = async (query, overrideThreadId) => {
    if (!query.trim()) return;
    const sentThreadId = overrideThreadId || activeId;
    const reqId = uid();

    // Set title on first message
    updateThread(sentThreadId, (h) => ({
      ...h,
      title:
        h.messages.length === 0
          ? query.slice(0, 32) + (query.length > 32 ? '…' : '')
          : h.title,
      messages: [...h.messages, { role: 'user', content: query }],
    }));

    setInput('');
    addLoading(sentThreadId, reqId);

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ query, thread_id: sentThreadId }),
      });

      if (res.status === 401) {
        onLogout();
        return;
      }
      const data = await res.json();

      if (data.status === 'needs_approval') {
        appendMsg(sentThreadId, {
          role: 'system',
          content: data.response,
          awaitingApproval: true,
        });
      } else {
        appendMsg(sentThreadId, { role: 'assistant', content: data.response });
      }

      // Backend /query automatically saves the turn to SQLite!
    } catch (_) {
      appendMsg(sentThreadId, {
        role: 'assistant',
        content: '⚠️ Error connecting to server.',
      });
    } finally {
      removeLoading(sentThreadId, reqId);
    }
  };

  // ── APPROVE / DENY ───────────────────────────────────────────────────────
  const handleResume = async (approved) => {
    const sentThreadId = activeId;
    const reqId = uid();

    updateThread(sentThreadId, (h) => ({
      ...h,
      messages: h.messages.map((m) =>
        m.role === 'system' && m.awaitingApproval
          ? { ...m, awaitingApproval: false }
          : m
      ),
    }));

    appendMsg(sentThreadId, {
      role: 'status',
      content: approved ? '✓ Action approved — executing…' : '✗ Action denied.',
    });
    addLoading(sentThreadId, reqId);

    try {
      const res = await fetch(`${API_BASE}/resume`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ thread_id: sentThreadId, approved }),
      });
      const data = await res.json();
      appendMsg(sentThreadId, { role: 'assistant', content: data.response });
    } catch (_) {
      appendMsg(sentThreadId, {
        role: 'assistant',
        content: '⚠️ Error resuming action.',
      });
    } finally {
      removeLoading(sentThreadId, reqId);
    }
  };

  /* ── BACKGROUND LOADING INDICATOR in sidebar ──────────────────────────── */
  const threadIsLoading = (item) => (item.loadingIds || []).length > 0;

  /* ── AVATARS ──────────────────────────────────────────────────────────── */
  const BotAvatar = () => (
    <div className="w-7 h-7 rounded-md bg-neutral-950 text-white flex items-center justify-center text-xs font-semibold shrink-0">
      M
    </div>
  );

  /* ── RENDER ───────────────────────────────────────────────────── */
  return (
    <div className="flex h-screen w-full bg-white text-neutral-900 relative overflow-hidden">
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-neutral-900/30 backdrop-blur-xs z-30 md:hidden transition-opacity"
        />
      )}

      {/* ── SIDEBAR ──────────────────────────────────────────────────────── */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-40 w-64 flex flex-col bg-neutral-50 border-r border-neutral-200 transition-transform duration-200 ease-in-out
          md:static md:translate-x-0
          ${sidebarOpen ? 'translate-x-0 shadow-2xl md:shadow-none' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Brand Header */}
        <div className="h-14 px-4 flex items-center justify-between border-b border-neutral-200 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-md bg-neutral-950 text-white flex items-center justify-center text-xs font-semibold">
              M
            </div>
            <span className="font-semibold text-sm tracking-tight">
              Meridian Copilot
            </span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-1.5 rounded-md text-neutral-500 hover:text-neutral-950 hover:bg-neutral-200/70"
          >
            <X size={18} />
          </button>
        </div>

        {/* New chat button */}
        <div className="p-3 shrink-0">
          <button
            onClick={handleNewChat}
            className="w-full h-9 flex items-center justify-center gap-2 rounded-lg border border-neutral-300 bg-white text-sm font-medium text-neutral-800 hover:bg-neutral-100 transition-colors shadow-xs"
          >
            <Plus size={16} /> New chat
          </button>
        </div>

        {/* History list */}
        <div className="flex-1 overflow-y-auto px-3 pb-3">
          <div className="flex items-center justify-between px-2 pt-2 pb-1.5">
            <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-400">
              Recent Chats ({history.length})
            </p>
          </div>
          <div className="space-y-0.5">
            {history.map((item) => {
              const isSelected = activeId === item.id;
              return (
                <div
                  key={item.id}
                  onClick={() => handleSelectThread(item)}
                  className={`group relative w-full flex items-center gap-2.5 px-2.5 h-9 rounded-md text-sm text-left transition-colors cursor-pointer ${
                    isSelected
                      ? 'bg-neutral-200/80 text-neutral-950 font-medium'
                      : 'text-neutral-600 hover:bg-neutral-100'
                  }`}
                >
                  {threadIsLoading(item) ? (
                    <Loader2
                      size={14}
                      className="shrink-0 text-neutral-400 animate-spin"
                    />
                  ) : (
                    <MessageSquare
                      size={15}
                      className="shrink-0 text-neutral-400"
                    />
                  )}
                  <span className="truncate flex-1 pr-6">{item.title}</span>
                  <button
                    onClick={(e) => handleDeleteThread(e, item.id)}
                    title="Delete conversation"
                    className="opacity-0 group-hover:opacity-100 p-1 text-neutral-400 hover:text-red-600 rounded transition-opacity"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* User profile footer */}
        <div className="border-t border-neutral-200 p-3 shrink-0">
          <div className="flex items-center gap-3 px-1">
            <div className="w-8 h-8 rounded-full bg-neutral-200 text-neutral-700 flex items-center justify-center text-xs font-semibold shrink-0">
              {initials(userProfile?.name)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium truncate">
                {userProfile?.name || 'Loading…'}
              </p>
              <p className="text-xs text-neutral-500 truncate">
                {userProfile
                  ? `${userProfile.role} · ${userProfile.department}`
                  : ''}
              </p>
            </div>
            <button
              onClick={onLogout}
              title="Sign out"
              className="p-2 rounded-md text-neutral-500 hover:text-neutral-950 hover:bg-neutral-200/70 transition-colors"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── MAIN AREA ────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Header */}
        <header className="h-14 px-4 md:px-6 flex items-center justify-between border-b border-neutral-200 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* Sidebar toggle button (works on all screen sizes) */}
            <button
              onClick={() => setSidebarOpen((prev) => !prev)}
              className="p-1.5 rounded-lg border border-neutral-200 hover:bg-neutral-100 text-neutral-600 transition cursor-pointer"
              title="Toggle chat history sidebar"
            >
              <Menu size={18} />
            </button>
            <h1 className="text-sm font-semibold truncate">
              {activeThread?.title || 'New conversation'}
            </h1>
            {isActiveLoading && (
              <Loader2
                size={14}
                className="text-neutral-400 animate-spin shrink-0"
              />
            )}
          </div>
          {userProfile?.role && (
            <span className="text-xs font-medium text-neutral-600 border border-neutral-300 rounded-full px-2.5 py-0.5 capitalize shrink-0">
              {userProfile.role}
            </span>
          )}
        </header>

        {/* Messages list */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-6 py-8 space-y-7">
            {/* Empty state */}
            {messages.length === 0 && !isActiveLoading && (
              <div className="pt-24 text-center">
                <div className="w-11 h-11 mx-auto rounded-lg bg-neutral-950 text-white flex items-center justify-center font-semibold">
                  M
                </div>
                <h2 className="mt-5 text-xl font-semibold tracking-tight text-neutral-950">
                  How can I help you today?
                </h2>
                <p className="mt-2 text-sm text-neutral-500 max-w-md mx-auto">
                  Ask about HR policies, IT support or Finance guidelines. All
                  conversations are securely saved to your account.
                </p>
                <div className="mt-8 flex flex-wrap justify-center gap-3">
                  {[
                    'What is the leave policy?',
                    'How do I file an expense claim?',
                    'What is the per diem for travel?',
                  ].map((s) => (
                    <button
                      key={s}
                      onClick={() => sendQuery(s)}
                      className="rounded-lg border border-neutral-200 px-4 py-3 text-sm text-neutral-700 hover:border-neutral-400 hover:bg-neutral-50 transition-colors shadow-2xs cursor-pointer"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Message items */}
            {messages.map((msg, i) => {
              if (msg.role === 'user') {
                return (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-md bg-neutral-100 border border-neutral-200 px-4 py-2.5 shadow-2xs">
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-900">
                        {msg.content}
                      </p>
                    </div>
                  </div>
                );
              }

              if (msg.role === 'system') {
                const isActionable =
                  msg.awaitingApproval && i === messages.length - 1;
                return (
                  <div key={i} className="flex gap-3">
                    <div className="w-7 h-7 rounded-md border border-neutral-300 bg-white flex items-center justify-center shrink-0">
                      <ShieldAlert size={15} className="text-neutral-700" />
                    </div>
                    <div className="flex-1 rounded-lg border border-neutral-300 border-l-4 border-l-neutral-950 bg-neutral-50 px-4 py-3">
                      <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500 mb-1.5">
                        Approval required
                      </p>
                      <div className="prose prose-sm max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                      {isActionable && (
                        <div className="mt-4 flex gap-2">
                          <button
                            onClick={() => handleResume(true)}
                            className="h-9 px-4 rounded-lg bg-neutral-950 text-white text-sm font-medium hover:bg-neutral-800 transition-colors"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleResume(false)}
                            className="h-9 px-4 rounded-lg border border-neutral-300 bg-white text-sm font-medium text-neutral-800 hover:bg-neutral-100 transition-colors"
                          >
                            Deny
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              }

              if (msg.role === 'status') {
                return (
                  <p key={i} className="text-center text-xs text-neutral-400">
                    {msg.content}
                  </p>
                );
              }

              // Assistant message
              return (
                <div key={i} className="flex gap-3">
                  <BotAvatar />
                  <div className="flex-1 min-w-0 pt-0.5 prose prose-sm max-w-none md leading-relaxed">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {withCitations(msg.content)}
                    </ReactMarkdown>
                  </div>
                </div>
              );
            })}

            {/* In-flight loading indicator */}
            {isActiveLoading && (
              <div className="flex gap-3 items-center">
                <BotAvatar />
                <div className="flex gap-1 py-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce [animation-delay:-0.3s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce [animation-delay:-0.15s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-neutral-400 animate-bounce" />
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input footer */}
        <div className="shrink-0 px-6 pb-5 pt-2">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendQuery(input);
            }}
            className="max-w-3xl mx-auto"
          >
            <div className="flex items-center gap-2 rounded-xl border border-neutral-300 bg-white pl-4 pr-2 py-2 shadow-sm focus-within:border-neutral-900 focus-within:ring-1 focus-within:ring-neutral-900 transition">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  pendingTool
                    ? 'Approve or deny the action above to continue'
                    : 'Message Meridian Copilot'
                }
                className="flex-1 bg-transparent text-sm placeholder:text-neutral-400 focus:outline-none disabled:cursor-not-allowed"
                disabled={isActiveLoading || !!pendingTool}
              />
              <button
                type="submit"
                disabled={isActiveLoading || !!pendingTool || !input.trim()}
                className="w-9 h-9 flex items-center justify-center rounded-lg bg-neutral-950 text-white hover:bg-neutral-800 disabled:bg-neutral-200 disabled:text-neutral-400 disabled:cursor-not-allowed transition-colors"
              >
                <ArrowUp size={18} />
              </button>
            </div>
            <p className="mt-2 text-center text-[11px] text-neutral-400">
              Responses may contain errors. Verify important information with
              the relevant team.
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
