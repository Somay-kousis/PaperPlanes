import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Plus, Send, MessageSquare, WifiOff, Loader2 } from "lucide-react";

import { createSession, listSessions, sendMessage, listMessages } from "../lib/api.js";
import MessageBubble from "../components/MessageBubble.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import EmptyState from "../components/EmptyState.jsx";

const SUGGESTED_PROMPTS = [
  { text: "What are the latest claims you extracted from my papers?" },
  { text: "Do any of my library papers contradict each other?" },
  { text: "How does the bi-temporal memory system work in CockroachDB?" },
  { text: "Give me a summary of research questions that remain open." },
];

export default function ChatPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [creatingSession, setCreatingSession] = useState(false);
  const [error, setError] = useState(null);
  const [echoMode, setEchoMode] = useState(false);
  const threadRef = useRef(null);

  const loadSessions = useCallback(async (options = {}) => {
    setSessionsLoading(true);
    try {
      const data = await listSessions(options);
      setSessions(data);
      setError(null);
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err);
      }
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadSessions({ signal: controller.signal });
    return () => { controller.abort(); };
  }, [loadSessions]);

  useEffect(() => {
    setEchoMode(false);
    if (!sessionId) { setMessages([]); return; }
    
    const controller = new AbortController();
    (async () => {
      try {
        const data = await listMessages(sessionId, { signal: controller.signal });
        setMessages(Array.isArray(data) ? data : (data?.messages ?? []));
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err);
        }
      }
    })();
    return () => { controller.abort(); };
  }, [sessionId]);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages]);

  async function handleNewSession() {
    if (creatingSession) return;
    setCreatingSession(true);
    try {
      const session = await createSession();
      const id = session?.id ?? session?.session_id;
      setError(null);
      await loadSessions();
      if (id) navigate(`/chat/${id}`);
    } catch (err) {
      setError(err);
    } finally {
      setCreatingSession(false);
    }
  }

  async function handleSend(event, customText) {
    if (event) event.preventDefault();
    const text = (customText || draft).trim();
    if (!text || sending || creatingSession) return;

    let activeSessionId = sessionId;
    setSending(true);
    if (!customText) setDraft("");

    try {
      if (!activeSessionId) {
        setCreatingSession(true);
        const session = await createSession();
        activeSessionId = session?.id ?? session?.session_id;
        if (activeSessionId) navigate(`/chat/${activeSessionId}`, { replace: true });
        await loadSessions();
        setCreatingSession(false);
      }

      const userMessage = { role: "user", content: text, created_at: new Date().toISOString() };
      setMessages((prev) => [...prev, userMessage, { role: "assistant", pending: true }]);

      const response = await sendMessage(activeSessionId, text);
      const reply = response?.reply ?? response;
      const meta = response?.meta;

      if (meta?.degraded || meta?.used_model === "echo") setEchoMode(true);

      setMessages((prev) => {
        const next = prev.slice(0, -1);
        next.push({
          role: reply?.role ?? "assistant",
          content: reply?.content ?? reply?.text ?? JSON.stringify(reply),
          created_at: reply?.created_at ?? new Date().toISOString(),
          citations: reply?.citations,
          memory_citations: reply?.memory_citations,
        });
        return next;
      });
      setError(null);
    } catch (err) {
      setCreatingSession(false);
      setMessages((prev) => prev.slice(0, -1));
      setError(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="inner-page">
      <div className="brutalist-container">

        {/* ── Page Header ──────────────────────────────────────────────── */}
        <header className="page-header">
          <div className="page-header-left">
            <div className="page-counter">
              <span className="page-counter-num">02 / Chat</span>
            </div>
            <h2 className="inner-h2">Chat Agent Console</h2>
            <p className="page-subtitle">
              Query the agent's memory or retrieve cited paragraphs from ingested publications.
            </p>
          </div>
          <div className="page-header-actions">
            <button
              className="brutalist-btn brutalist-btn-primary brutalist-btn-sm"
              onClick={handleNewSession}
            >
              <Plus size={13} /> New Session
            </button>
          </div>
        </header>

        {error && (
          <ErrorBanner title="Chat Connection Alert" message={error.message} onDismiss={() => setError(null)} />
        )}

        {/* ── Chat Layout ──────────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: "var(--space-md)", alignItems: "start" }}>

          {/* Sessions Sidebar */}
          <div
            className="app-card"
            style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column", gap: "var(--space-xs)", height: "620px", overflowY: "auto" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: "var(--space-xs)", borderBottom: "1px solid var(--border-ui)", marginBottom: "4px" }}>
              <span className="mono-upper" style={{ color: "var(--fg-muted)" }}>Sessions</span>
            </div>

            {sessionsLoading ? (
              <p className="text-muted" style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                <Loader2 size={11} className="icon-spin" /> Loading...
              </p>
            ) : sessions.length === 0 ? (
              <p className="text-muted">No sessions yet.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                {sessions.map((session) => {
                  const id = session.id ?? session.session_id;
                  const active = id === sessionId;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => navigate(`/chat/${id}`)}
                      style={{
                        padding: "9px 10px",
                        border: active ? "1px solid var(--accent-cobalt)" : "1px solid var(--border-ui)",
                        borderRadius: "5px",
                        backgroundColor: active ? "var(--accent-cobalt-light)" : "var(--bg-card)",
                        textAlign: "left",
                        cursor: "pointer",
                        width: "100%",
                        outline: "none",
                        transition: "background 0.15s ease",
                      }}
                    >
                      <div
                        style={{ fontWeight: active ? 600 : 400, fontSize: "0.88rem", color: "var(--fg-navy)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                      >
                        {session.title || `Session ${String(id).slice(0, 8)}`}
                      </div>
                      {session.created_at && (
                        <div className="mono" style={{ fontSize: "0.7rem", color: "var(--fg-muted)", marginTop: "2px" }}>
                          {new Date(session.created_at).toLocaleDateString()}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Chat Feed */}
          <div
            className="app-card"
            style={{ display: "flex", flexDirection: "column", height: "620px" }}
          >
            {/* Messages area */}
            <div style={{ flex: 1, padding: "var(--space-md)", overflowY: "auto" }} ref={threadRef}>
              {echoMode && (
                <div
                  style={{ display: "flex", gap: "7px", alignItems: "center", backgroundColor: "var(--accent-red-light)", border: "1px solid var(--accent-red)", borderRadius: "5px", padding: "8px 12px", color: "var(--accent-red)", marginBottom: "var(--space-sm)", fontSize: "0.82rem" }}
                  className="mono"
                >
                  <WifiOff size={13} /> Running in echo mode — no model credentials connected.
                </div>
              )}

              {!sessionId && messages.length === 0 ? (
                <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "var(--space-md)", textAlign: "center" }}>
                  <EmptyState
                    icon={MessageSquare}
                    title="Initialize Conversation"
                    description="Select a session thread or send a direct prompt below."
                  />
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", maxWidth: "560px" }}>
                    {SUGGESTED_PROMPTS.map((prompt, idx) => (
                      <button
                        key={idx}
                        type="button"
                        style={{
                          padding: "12px var(--space-sm)",
                          border: "1px solid var(--border-ui)",
                          borderRadius: "6px",
                          backgroundColor: "var(--bg-cream)",
                          textAlign: "left",
                          cursor: "pointer",
                          transition: "box-shadow 0.15s ease",
                        }}
                        onClick={() => handleSend(null, prompt.text)}
                        onMouseOver={(e) => e.currentTarget.style.boxShadow = "var(--shadow-card-hover)"}
                        onMouseOut={(e) => e.currentTarget.style.boxShadow = "none"}
                      >
                        <p style={{ fontSize: "0.83rem", fontWeight: 600, color: "var(--fg-navy)", lineHeight: 1.4 }}>{prompt.text}</p>
                        <span style={{ fontSize: "0.72rem", color: "var(--accent-cobalt)", fontWeight: 700, fontFamily: "var(--font-mono)", marginTop: "4px", display: "block" }}>Ask agent →</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((msg, index) => (
                  <MessageBubble
                    key={index}
                    role={msg.role}
                    content={msg.content}
                    createdAt={msg.created_at}
                    citations={msg.citations}
                    memoryCitations={msg.memory_citations}
                    pending={msg.pending}
                  />
                ))
              )}
            </div>

            {/* Composer */}
            <form
              onSubmit={handleSend}
              style={{
                borderTop: "1px solid var(--border-ui)",
                padding: "var(--space-sm)",
                display: "flex",
                gap: "var(--space-sm)",
                backgroundColor: "var(--bg-cream)",
                alignItems: "center",
                borderRadius: "0 0 6px 6px",
              }}
            >
              <textarea
                placeholder="Query the PaperPlanes memory agent…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend(e);
                  }
                }}
                rows={1}
                className="app-input"
                style={{ resize: "none" }}
              />
              <button
                type="submit"
                className="brutalist-btn brutalist-btn-primary brutalist-btn-sm"
                disabled={sending || !draft.trim()}
                style={{ flexShrink: 0 }}
              >
                <Send size={13} />
              </button>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
}
