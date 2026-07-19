import { useCallback, useEffect, useState } from "react";
import { Brain, History, Loader2, Search, Sparkles } from "lucide-react";

import {
  getMemoryNotes,
  getMemoryNote,
  getAudit,
  getMemoryStats,
  getReflections,
  runReflection,
} from "../lib/api.js";
import { localInputToIso } from "../lib/format.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import MemoryStatsHeader from "../components/memory/MemoryStatsHeader.jsx";
import TimeTravelBanner from "../components/memory/TimeTravelBanner.jsx";
import NoteRow from "../components/memory/NoteRow.jsx";
import NoteDetail from "../components/memory/NoteDetail.jsx";
import AuditRow from "../components/memory/AuditRow.jsx";
import ReflectionCard from "../components/memory/ReflectionCard.jsx";

const STATUS_OPTIONS = ["active", "archived", "invalidated", "all"];
const AUDIT_ACTIONS = ["", "add", "update", "invalidate", "archive", "read"];
const POLL_INTERVAL_MS = 5000;
const SEARCH_DEBOUNCE_MS = 300;

const TABS = [
  { key: "notes",       label: "Facts",        icon: Brain },
  { key: "audit",       label: "Transactions", icon: History },
  { key: "reflections", label: "Reflections",  icon: Sparkles },
];

export default function MemoryInspectorPage() {
  const [activeTab, setActiveTab] = useState("notes");

  const [statusFilter, setStatusFilter]   = useState("active");
  const [searchInput, setSearchInput]     = useState("");
  const [searchQuery, setSearchQuery]     = useState("");
  const [asOfInput, setAsOfInput]         = useState("");
  const [notes, setNotes]                 = useState([]);
  const [notesLoading, setNotesLoading]   = useState(true);
  const [notesError, setNotesError]       = useState(null);

  const [auditActionFilter, setAuditActionFilter] = useState("");
  const [auditItems, setAuditItems]   = useState([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError, setAuditError]   = useState(null);

  const [stats, setStats]               = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const [reflections, setReflections]         = useState([]);
  const [reflectionsLoading, setReflectionsLoading] = useState(true);
  const [reflectionsError, setReflectionsError]   = useState(null);
  const [reflectionRunning, setReflectionRunning]  = useState(false);
  const [reflectionResultMsg, setReflectionResultMsg] = useState("");
  const [unavailableCiteIds, setUnavailableCiteIds] = useState(() => new Set());

  const [selectedNoteId, setSelectedNoteId] = useState(null);
  const [selectedNote, setSelectedNote]     = useState(null);
  const [detailLoading, setDetailLoading]   = useState(false);
  const [detailError, setDetailError]       = useState(null);

  const asOfIso = asOfInput ? localInputToIso(asOfInput) : "";

  useEffect(() => {
    const t = setTimeout(() => setSearchQuery(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchInput]);

  const fetchNotes = useCallback(
    async ({ silent = false, options = {} } = {}) => {
      if (!silent) setNotesLoading(true);
      try {
        const params = { q: searchQuery || undefined, limit: 50 };
        if (asOfIso) params.as_of = asOfIso;
        else params.status = statusFilter;
        const data = await getMemoryNotes(params, options);
        setNotes(data);
        setNotesError(null);
      } catch (err) {
        if (err.name !== "AbortError") {
          setNotesError(err);
        }
      } finally {
        if (!silent) setNotesLoading(false);
      }
    },
    [statusFilter, searchQuery, asOfIso],
  );

  const fetchStats = useCallback(async (options = {}) => {
    try {
      const data = await getMemoryStats(options);
      setStats(data);
    } catch {}
  }, []);

  const fetchAudit = useCallback(async (options = {}) => {
    setAuditLoading(true);
    try {
      const data = await getAudit({ action: auditActionFilter || undefined, limit: 100 }, options);
      setAuditItems(data);
      setAuditError(null);
    } catch (err) {
      if (err.name !== "AbortError") {
        setAuditError(err);
      }
    } finally {
      setAuditLoading(false);
    }
  }, [auditActionFilter]);

  const openNote = useCallback(async (id) => {
    if (!id) return false;
    setSelectedNoteId(id);
    setDetailLoading(true);
    try {
      const data = await getMemoryNote(id);
      setSelectedNote(data);
      setDetailError(null);
      return true;
    } catch (err) {
      setDetailError(err);
      setSelectedNote(null);
      return false;
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const fetchReflections = useCallback(async (options = {}) => {
    setReflectionsLoading(true);
    try {
      const data = await getReflections(options);
      setReflections(data);
      setReflectionsError(null);
    } catch (err) {
      if (err.name !== "AbortError") {
        setReflectionsError(err);
      }
    } finally {
      setReflectionsLoading(false);
    }
  }, []);

  const openCitedNote = useCallback(
    async (id) => {
      if (!id || unavailableCiteIds.has(id)) return;
      const ok = await openNote(id);
      if (!ok) setUnavailableCiteIds((prev) => new Set(prev).add(id));
    },
    [openNote, unavailableCiteIds],
  );

  async function handleRunReflection() {
    setReflectionRunning(true);
    setReflectionResultMsg("");
    try {
      const result = await runReflection();
      const created = result?.reflections_created ?? 0;
      const archived = result?.notes_archived ?? 0;
      setReflectionResultMsg(
        `Consolidation complete: ${created} reflection${created === 1 ? "" : "s"} created, ${archived} note${archived === 1 ? "" : "s"} archived.`,
      );
      await Promise.all([fetchReflections(), fetchStats()]);
    } catch (err) {
      setReflectionResultMsg(`Reflection failed: ${err.message}`);
    } finally {
      setReflectionRunning(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetchNotes({ options: { signal: controller.signal } });
    return () => { controller.abort(); };
  }, [fetchNotes]);

  useEffect(() => {
    const controller = new AbortController();
    setStatsLoading(true);
    fetchStats({ signal: controller.signal }).finally(() => {
      if (!controller.signal.aborted) {
        setStatsLoading(false);
      }
    });
    return () => { controller.abort(); };
  }, [fetchStats]);

  useEffect(() => {
    if (activeTab !== "audit") return;
    const controller = new AbortController();
    fetchAudit({ signal: controller.signal });
    return () => { controller.abort(); };
  }, [activeTab, fetchAudit]);

  useEffect(() => {
    if (activeTab !== "reflections") return;
    const controller = new AbortController();
    fetchReflections({ signal: controller.signal });
    return () => { controller.abort(); };
  }, [activeTab, fetchReflections]);

  useEffect(() => {
    if (asOfIso || activeTab !== "notes") return;
    const controller = new AbortController();
    let inFlight = false;

    async function tick() {
      if (document.visibilityState !== "visible" || inFlight || controller.signal.aborted) return;
      inFlight = true;
      try {
        await Promise.all([
          fetchNotes({ silent: true, options: { signal: controller.signal } }),
          fetchStats({ signal: controller.signal }),
        ]);
      } finally {
        inFlight = false;
      }
    }
    const id = setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
      controller.abort();
    };
  }, [asOfIso, activeTab, fetchNotes, fetchStats]);

  const listError = activeTab === "notes" ? notesError : activeTab === "audit" ? auditError : reflectionsError;
  const dismissListError = activeTab === "notes"
    ? () => setNotesError(null)
    : activeTab === "audit"
    ? () => setAuditError(null)
    : () => setReflectionsError(null);

  return (
    <div className="inner-page">
      <div className="brutalist-container">

        {/* ── Page Header ──────────────────────────────────────────────── */}
        <header className="page-header">
          <div className="page-header-left">
            <div className="page-counter">
              <span className="page-counter-num">03 / Memory</span>
            </div>
            <h2 className="inner-h2">Memory Inspector</h2>
            <p className="page-subtitle">
              Explore the bi-temporal memory layer, trace updates, and trigger manual consolidations.
            </p>
          </div>
          <div className="page-header-actions">
            <button
              type="button"
              className="brutalist-btn brutalist-btn-primary brutalist-btn-sm"
              onClick={handleRunReflection}
              disabled={reflectionRunning}
            >
              {reflectionRunning ? <Loader2 size={12} className="icon-spin" /> : <Sparkles size={12} />}
              {reflectionRunning ? "Consolidating…" : "Run Reflection"}
            </button>
          </div>
        </header>

        {/* Stats row */}
        <MemoryStatsHeader stats={stats} loading={statsLoading} />

        {/* Reflection result banner */}
        {reflectionResultMsg && (
          <div
            style={{ padding: "9px 14px", border: "1px solid var(--accent-cobalt)", backgroundColor: "var(--accent-cobalt-light)", borderRadius: "5px", fontSize: "0.82rem", color: "var(--accent-cobalt)", marginBottom: "var(--space-sm)", fontFamily: "var(--font-mono)" }}
          >
            {reflectionResultMsg}
          </div>
        )}

        <TimeTravelBanner asOf={asOfIso} onClear={() => setAsOfInput("")} />

        {listError && <ErrorBanner title="Connection Alert" message={listError.message} onDismiss={dismissListError} />}
        {detailError && <ErrorBanner title="Detail Load Failed" message={detailError.message} onDismiss={() => setDetailError(null)} />}

        {/* ── Tab Bar + Filter Bar ─────────────────────────────────────── */}
        <div className="app-card" style={{ padding: "var(--space-sm)", marginBottom: "var(--space-md)" }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-md)", alignItems: "center" }}>

            {/* Tab switcher */}
            <div className="tab-bar" style={{ borderBottom: "none", gap: "0" }}>
              {TABS.map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  type="button"
                  className={`tab-btn${activeTab === key ? " active" : ""}`}
                  onClick={() => setActiveTab(key)}
                >
                  <Icon size={13} /> {label}
                </button>
              ))}
            </div>

            {/* Status/action filter pills */}
            <div className="filter-pill-group">
              {activeTab === "notes"
                ? STATUS_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      className={`filter-pill${statusFilter === opt ? " active" : ""}`}
                      disabled={Boolean(asOfIso)}
                      onClick={() => setStatusFilter(opt)}
                    >
                      {opt}
                    </button>
                  ))
                : activeTab === "audit"
                ? AUDIT_ACTIONS.map((opt) => (
                    <button
                      key={opt || "all"}
                      className={`filter-pill${auditActionFilter === opt ? " active" : ""}`}
                      onClick={() => setAuditActionFilter(opt)}
                    >
                      {opt || "all"}
                    </button>
                  ))
                : null}
            </div>

            {/* Search input */}
            <div style={{ display: "flex", alignItems: "center", gap: "7px", border: "1px solid var(--border-ui)", borderRadius: "5px", padding: "5px 10px", backgroundColor: "var(--bg-card)" }}>
              <Search size={13} style={{ color: "var(--fg-muted)", flexShrink: 0 }} />
              <input
                type="text"
                placeholder="Search facts…"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                disabled={activeTab !== "notes"}
                style={{ border: "none", fontSize: "0.88rem", outline: "none", width: "140px", fontFamily: "var(--font-sans)", color: "var(--fg-navy)", background: "transparent" }}
              />
            </div>

            {/* Time travel picker */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <label htmlFor="asof-field" className="mono-upper" style={{ color: "var(--fg-muted)", fontSize: "0.65rem" }}>As of</label>
              <input
                id="asof-field"
                type="datetime-local"
                value={asOfInput}
                onChange={(e) => setAsOfInput(e.target.value)}
                disabled={activeTab !== "notes"}
                className="app-input"
                style={{ width: "auto", fontSize: "0.82rem", padding: "5px 9px" }}
              />
            </div>

          </div>
        </div>

        {/* ── Main Split Layout ─────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-md)", alignItems: "start" }}>

          {/* Left: log list */}
          <div className="app-card app-card-red" style={{ padding: "var(--space-sm)", height: "600px", overflowY: "auto" }}>
            {activeTab === "notes" ? (
              notesLoading ? (
                <p className="text-muted" style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <Loader2 size={12} className="icon-spin" /> Loading memory facts…
                </p>
              ) : notes.length === 0 ? (
                <EmptyState icon={Brain} title="No facts recorded" description="Ask the agent questions in Chat to build semantic fact structures." />
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                  {notes.map((note) => (
                    <NoteRow key={note.id} note={note} selected={note.id === selectedNoteId} onClick={() => openNote(note.id)} />
                  ))}
                </div>
              )
            ) : activeTab === "audit" ? (
              auditLoading ? (
                <p className="text-muted" style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                  <Loader2 size={12} className="icon-spin" /> Loading transaction logs…
                </p>
              ) : auditItems.length === 0 ? (
                <EmptyState icon={History} title="No transaction records" description="Audit trails log when facts are added, updated, read, or invalidated." />
              ) : (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {auditItems.map((entry) => <AuditRow key={entry.id} entry={entry} showTarget onOpenNote={openNote} />)}
                </div>
              )
            ) : reflectionsLoading ? (
              <p className="text-muted" style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                <Loader2 size={12} className="icon-spin" /> Loading consolidations…
              </p>
            ) : reflections.length === 0 ? (
              <EmptyState icon={Sparkles} title="No reflections distilled" description="Click 'Run Reflection' or wait for the system to consolidate automatically." />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                {reflections.map((r) => (
                  <ReflectionCard key={r.id} reflection={r} unavailableCiteIds={unavailableCiteIds} onOpenCite={openCitedNote} />
                ))}
              </div>
            )}
          </div>

          {/* Right: detail + graph */}
          <div className="app-card" style={{ padding: "var(--space-sm)", minHeight: "400px" }}>
            <NoteDetail note={selectedNote} loading={detailLoading} onOpenNote={openNote} />
          </div>

        </div>
      </div>
    </div>
  );
}
