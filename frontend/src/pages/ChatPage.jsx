import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Plus, Send, MessageSquare, WifiOff } from "lucide-react";

import { createSession, listSessions, sendMessage, listMessages } from "../lib/api.js";
import MessageBubble from "../components/MessageBubble.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import EmptyState from "../components/EmptyState.jsx";
import use3dTilt from "../lib/use3dTilt.js";

export default function ChatPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const cardTilt = use3dTilt(6, 1.025);

  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [echoMode, setEchoMode] = useState(false);
  const threadRef = useRef(null);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await listSessions();
      setSessions(data);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    setEchoMode(false);
    if (!sessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const data = await listMessages(sessionId);
        if (!cancelled) setMessages(Array.isArray(data) ? data : (data?.messages ?? []));
      } catch (err) {
        if (!cancelled) setError(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleNewSession() {
    try {
      const session = await createSession();
      const id = session?.id ?? session?.session_id;
      setError(null);
      await loadSessions();
      if (id) navigate(`/chat/${id}`);
    } catch (err) {
      setError(err);
    }
  }

  async function handleSend(event, customText) {
    if (event) event.preventDefault();
    const text = (customText || draft).trim();
    if (!text || sending) return;

    let activeSessionId = sessionId;

    setSending(true);
    if (!customText) setDraft("");

    try {
      if (!activeSessionId) {
        const session = await createSession();
        activeSessionId = session?.id ?? session?.session_id;
        if (activeSessionId) navigate(`/chat/${activeSessionId}`, { replace: true });
        await loadSessions();
      }

      const userMessage = { role: "user", content: text, created_at: new Date().toISOString() };
      setMessages((prev) => [...prev, userMessage, { role: "assistant", pending: true }]);

      const response = await sendMessage(activeSessionId, text);
      const reply = response?.reply ?? response;
      const meta = response?.meta;

      if (meta?.degraded || meta?.used_model === "echo") {
        setEchoMode(true);
      }

      setMessages((prev) => {
        const next = prev.slice(0, -1); // drop pending bubble
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
      setMessages((prev) => prev.slice(0, -1)); // drop pending bubble on failure
      setError(err);
    } finally {
      setSending(false);
    }
  }

  const SUGGESTED_PROMPTS = [
    { text: "What are the latest claims you extracted from my papers?" },
    { text: "Do any of my library papers contradict each other?" },
    { text: "How does the bi-temporal memory system work in CockroachDB?" },
    { text: "Give me a summary of research questions that remain open." }
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Chat</h1>
          <p className="page-subtitle">Ask a question, PaperPlanes answers from its memory.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={handleNewSession}>
          <Plus size={15} /> New session
        </button>
      </div>

      {error && (
        <ErrorBanner
          title="Backend unreachable"
          message={error.message}
          onDismiss={() => setError(null)}
        />
      )}

      <div className="chat-layout">
        <div className="card session-list">
          {sessionsLoading && <p className="text-muted">Loading sessions…</p>}
          {!sessionsLoading && sessions.length === 0 && (
            <p className="text-muted">No sessions yet. Start one below.</p>
          )}
          {sessions.map((session) => {
            const id = session.id ?? session.session_id;
            return (
              <button
                key={id}
                type="button"
                className={"session-item" + (id === sessionId ? " active" : "")}
                onClick={() => navigate(`/chat/${id}`)}
              >
                <span className="session-item-title">{session.title || `Session ${id}`}</span>
                <span className="session-item-meta">{session.created_at ?? ""}</span>
              </button>
            );
          })}
        </div>

        <div className="card chat-panel">
          {!sessionId && messages.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", flex: 1, padding: "var(--space-5)" }}>
              <EmptyState
                icon={MessageSquare}
                title="Start a conversation"
                description="Send a message below or select a suggested prompt to spin up a new session against PaperPlanes."
              />
              <div className="suggested-prompts-grid">
                {SUGGESTED_PROMPTS.map((prompt, index) => (
                  <button
                    key={index}
                    type="button"
                    className="suggested-prompt-card"
                    onMouseMove={cardTilt.onMouseMove}
                    onMouseLeave={cardTilt.onMouseLeave}
                    onMouseEnter={cardTilt.onMouseEnter}
                    onClick={() => handleSend(null, prompt.text)}
                  >
                    <span className="suggested-prompt-card-text">{prompt.text}</span>
                    <span className="suggested-prompt-card-action">Ask assistant &rarr;</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-thread" ref={threadRef}>
              {echoMode && (
                <div className="mode-notice">
                  <WifiOff size={14} />
                  Running in echo mode — no model connected.
                </div>
              )}
              {messages.map((message, index) => (
                <MessageBubble
                  key={index}
                  role={message.role}
                  content={message.content}
                  createdAt={message.created_at}
                  citations={message.citations}
                  memoryCitations={message.memory_citations}
                  pending={message.pending}
                />
              ))}
            </div>
          )}

          <form className="chat-composer" onSubmit={(e) => handleSend(e)}>
            <textarea
              className="textarea"
              rows={1}
              placeholder="Ask PaperPlanes about your papers…"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend(event);
                }
              }}
            />
            <button type="submit" className="btn btn-primary btn-icon" disabled={sending || !draft.trim()}>
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

