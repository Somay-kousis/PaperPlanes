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

export default function MemoryInspectorPage() {
  const [activeTab, setActiveTab] = useState("notes"); // "notes" | "audit" | "reflections"

  // Notes list state
  const [statusFilter, setStatusFilter] = useState("active");
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [asOfInput, setAsOfInput] = useState(""); // datetime-local raw value
  const [notes, setNotes] = useState([]);
  const [notesLoading, setNotesLoading] = useState(true);
  const [notesError, setNotesError] = useState(null);

  // Audit feed state
  const [auditActionFilter, setAuditActionFilter] = useState("");
  const [auditItems, setAuditItems] = useState([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [auditError, setAuditError] = useState(null);

  // Stats header
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Reflections tab state
  const [reflections, setReflections] = useState([]);
  const [reflectionsLoading, setReflectionsLoading] = useState(true);
  const [reflectionsError, setReflectionsError] = useState(null);
  const [reflectionRunning, setReflectionRunning] = useState(false);
  const [reflectionResultMsg, setReflectionResultMsg] = useState("");
  const [unavailableCiteIds, setUnavailableCiteIds] = useState(() => new Set());

  // Detail panel
  const [selectedNoteId, setSelectedNoteId] = useState(null);
  const [selectedNote, setSelectedNote] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  const asOfIso = asOfInput ? localInputToIso(asOfInput) : "";

  // Debounce free-text search input -> committed query param.
  useEffect(() => {
    const timer = setTimeout(() => setSearchQuery(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const fetchNotes = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setNotesLoading(true);
      try {
        const params = { q: searchQuery || undefined, limit: 50 };
        if (asOfIso) {
          params.as_of = asOfIso;
        } else {
          params.status = statusFilter;
        }
        const data = await getMemoryNotes(params);
        setNotes(data);
        setNotesError(null);
      } catch (err) {
        setNotesError(err);
      } finally {
        if (!silent) setNotesLoading(false);
      }
    },
    [statusFilter, searchQuery, asOfIso],
  );

  const fetchStats = useCallback(async () => {
    try {
      const data = await getMemoryStats();
      setStats(data);
    } catch {
      // Stats are a nice-to-have header; don't surface a banner for this.
    }
  }, []);

  const fetchAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const data = await getAudit({ action: auditActionFilter || undefined, limit: 100 });
      setAuditItems(data);
      setAuditError(null);
    } catch (err) {
      setAuditError(err);
    } finally {
      setAuditLoading(false);
    }
  }, [auditActionFilter]);

  /** Returns true on success, false if the note couldn't be loaded. */
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

  const fetchReflections = useCallback(async () => {
    setReflectionsLoading(true);
    try {
      const data = await getReflections();
      setReflections(data);
      setReflectionsError(null);
    } catch (err) {
      setReflectionsError(err);
    } finally {
      setReflectionsLoading(false);
    }
  }, []);

  // Best-effort: open a note cited by a reflection. If it can't be loaded
  // (archived away or deleted), grey the chip out for the rest of the session.
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
        `Created ${created} reflection${created === 1 ? "" : "s"}, archived ${archived} note${archived === 1 ? "" : "s"}.`,
      );
      await Promise.all([fetchReflections(), fetchStats()]);
    } catch (err) {
      setReflectionResultMsg(`Reflection run failed: ${err.message}`);
    } finally {
      setReflectionRunning(false);
    }
  }

  // Refetch notes whenever filters change (shows the loading state).
  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  // Stats: fetch once on mount.
  useEffect(() => {
    setStatsLoading(true);
    fetchStats().finally(() => setStatsLoading(false));
  }, [fetchStats]);

  // Audit feed: fetch whenever the tab is active or its filter changes.
  useEffect(() => {
    if (activeTab === "audit") fetchAudit();
  }, [activeTab, fetchAudit]);

  // Reflections: fetch whenever the tab becomes active.
  useEffect(() => {
    if (activeTab === "reflections") fetchReflections();
  }, [activeTab, fetchReflections]);

  // Live-update: poll the notes list + stats every 5s, but only while the
  // tab is visible and we're not looking at a fixed point in the past.
  useEffect(() => {
    if (asOfIso || activeTab !== "notes") return undefined;

    function tick() {
      if (document.visibilityState === "visible") {
        fetchNotes({ silent: true });
        fetchStats();
      }
    }

    const intervalId = setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [asOfIso, activeTab, fetchNotes, fetchStats]);

  const listError =
    activeTab === "notes" ? notesError : activeTab === "audit" ? auditError : reflectionsError;
  const dismissListError =
    activeTab === "notes"
      ? () => setNotesError(null)
      : activeTab === "audit"
        ? () => setAuditError(null)
        : () => setReflectionsError(null);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Memory Inspector</h1>
          <p className="page-subtitle">
            Browse every memory note PaperPlanes has stored, and audit how it changed over time.
          </p>
        </div>
      </div>

      <MemoryStatsHeader stats={stats} loading={statsLoading} />

      <div className="flex-row reflection-toolbar">
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleRunReflection}
          disabled={reflectionRunning}
        >
          {reflectionRunning ? <Loader2 size={14} className="icon-spin" /> : <Sparkles size={14} />}
          {reflectionRunning ? "Running…" : "Run reflection"}
        </button>
        {reflectionResultMsg && <span className="text-muted reflection-toolbar-msg">{reflectionResultMsg}</span>}
      </div>

      <TimeTravelBanner asOf={asOfIso} onClear={() => setAsOfInput("")} />

      <div className="card filter-bar">
        <div className="segmented" role="tablist" aria-label="Inspector view">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "notes"}
            className={"segmented-btn" + (activeTab === "notes" ? " active" : "")}
            onClick={() => setActiveTab("notes")}
          >
            <Brain size={13} /> Notes
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "audit"}
            className={"segmented-btn" + (activeTab === "audit" ? " active" : "")}
            onClick={() => setActiveTab("audit")}
          >
            <History size={13} /> Audit log
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "reflections"}
            className={"segmented-btn" + (activeTab === "reflections" ? " active" : "")}
            onClick={() => setActiveTab("reflections")}
          >
            <Sparkles size={13} /> Reflections
          </button>
        </div>

        {activeTab === "notes" ? (
          <div className="pill-toggle-group" role="group" aria-label="Status filter">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option}
                type="button"
                className={"pill-toggle" + (statusFilter === option ? " active" : "")}
                disabled={Boolean(asOfIso)}
                title={asOfIso ? "Status filter is ignored while time-traveling" : undefined}
                onClick={() => setStatusFilter(option)}
              >
                {option}
              </button>
            ))}
          </div>
        ) : activeTab === "audit" ? (
          <div className="pill-toggle-group" role="group" aria-label="Action filter">
            {AUDIT_ACTIONS.map((option) => (
              <button
                key={option || "all"}
                type="button"
                className={"pill-toggle" + (auditActionFilter === option ? " active" : "")}
                onClick={() => setAuditActionFilter(option)}
              >
                {option || "all"}
              </button>
            ))}
          </div>
        ) : null}

        <div className="filter-field search-field">
          <label htmlFor="memory-search">
            <Search size={11} /> Search
          </label>
          <input
            id="memory-search"
            className="input"
            placeholder="Search note content…"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            disabled={activeTab !== "notes"}
          />
        </div>

        <div className="filter-field">
          <label htmlFor="asof-filter">As of</label>
          <input
            id="asof-filter"
            type="datetime-local"
            className="input"
            value={asOfInput}
            onChange={(event) => setAsOfInput(event.target.value)}
            disabled={activeTab !== "notes"}
          />
        </div>
      </div>

      {listError && (
        <ErrorBanner title="Could not reach the backend" message={listError.message} onDismiss={dismissListError} />
      )}
      {detailError && (
        <ErrorBanner
          title="Could not load that note"
          message={detailError.message}
          onDismiss={() => setDetailError(null)}
        />
      )}

      <div className="inspector-layout">
        <div className="card notes-pane">
          {activeTab === "notes" ? (
            notesLoading ? (
              <p className="text-muted pane-loading">Loading memories…</p>
            ) : notes.length === 0 ? (
              <EmptyState
                icon={Brain}
                title="No memories yet"
                description="Chat with PaperPlanes about your papers and it will start remembering."
              />
            ) : (
              <div className="notes-list">
                {notes.map((note) => (
                  <NoteRow
                    key={note.id}
                    note={note}
                    selected={note.id === selectedNoteId}
                    onClick={() => openNote(note.id)}
                  />
                ))}
              </div>
            )
          ) : activeTab === "audit" ? (
            auditLoading ? (
              <p className="text-muted pane-loading">Loading audit log…</p>
            ) : auditItems.length === 0 ? (
              <EmptyState
                icon={History}
                title="No audit entries yet"
                description="Every add, update, invalidate, archive, and read the agent performs on memory shows up here."
              />
            ) : (
              <div className="audit-trail audit-trail-feed">
                {auditItems.map((entry) => (
                  <AuditRow key={entry.id} entry={entry} showTarget onOpenNote={openNote} />
                ))}
              </div>
            )
          ) : reflectionsLoading ? (
            <p className="text-muted pane-loading">Loading reflections…</p>
          ) : reflections.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="No reflections yet"
              description="Click Run reflection, or let the background worker distill your memories over time."
            />
          ) : (
            <div className="reflections-list">
              {reflections.map((reflection) => (
                <ReflectionCard
                  key={reflection.id}
                  reflection={reflection}
                  unavailableCiteIds={unavailableCiteIds}
                  onOpenCite={openCitedNote}
                />
              ))}
            </div>
          )}
        </div>

        <div className="card side-panel">
          <NoteDetail note={selectedNote} loading={detailLoading} onOpenNote={openNote} />
        </div>
      </div>
    </div>
  );
}
