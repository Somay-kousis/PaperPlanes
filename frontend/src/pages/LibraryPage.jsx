import { useCallback, useEffect, useRef, useState } from "react";
import { UploadCloud, FileText, Link2, Loader2 } from "lucide-react";

import { listPapers, uploadPaper, addArxivPaper, deletePaper } from "../lib/api.js";
import { isTerminalStatus } from "../components/StatusBadge.jsx";
import PaperRow from "../components/PaperRow.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import EmptyState from "../components/EmptyState.jsx";

const POLL_INTERVAL_MS = 2500;

export default function LibraryPage() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [arxivValue, setArxivValue] = useState("");
  const [addingArxiv, setAddingArxiv] = useState(false);
  const [deletingIds, setDeletingIds] = useState(() => new Set());
  const [error, setError] = useState(null);

  const inputRef = useRef(null);
  const pollTimeoutRef = useRef(null);

  const loadPapers = useCallback(async ({ silent = false, options = {} } = {}) => {
    if (!silent) setLoading(true);
    try {
      const data = await listPapers(options);
      setPapers(data);
      setError(null);
      return data;
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err);
      }
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  const scheduleNextPoll = useCallback(
    (items, signal) => {
      if (pollTimeoutRef.current) return;
      const hasInProgress = (items ?? []).some((p) => !isTerminalStatus(p.status));
      if (!hasInProgress) return;
      pollTimeoutRef.current = setTimeout(async () => {
        pollTimeoutRef.current = null;
        if (signal?.aborted) return;
        const data = await loadPapers({ silent: true, options: { signal } });
        scheduleNextPoll(data, signal);
      }, POLL_INTERVAL_MS);
    },
    [loadPapers],
  );

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      const data = await loadPapers({ options: { signal: controller.signal } });
      if (!cancelled) scheduleNextPoll(data, controller.signal);
    })();
    return () => {
      cancelled = true;
      controller.abort();
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };
  }, [loadPapers, scheduleNextPoll]);

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (files.length === 0) return;
    setUploading(true);
    try {
      for (const file of files) await uploadPaper(file);
      const data = await loadPapers();
      scheduleNextPoll(data);
    } catch (err) {
      setError(err);
    } finally {
      setUploading(false);
    }
  }

  async function handleArxivSubmit(event) {
    event.preventDefault();
    const value = arxivValue.trim();
    if (!value || addingArxiv) return;
    setAddingArxiv(true);
    try {
      await addArxivPaper(value);
      setArxivValue("");
      const data = await loadPapers();
      scheduleNextPoll(data);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setAddingArxiv(false);
    }
  }

  async function handleDelete(paperId) {
    setDeletingIds((prev) => new Set(prev).add(paperId));
    try {
      await deletePaper(paperId);
      setPapers((prev) => prev.filter((p) => p.id !== paperId));
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev);
        next.delete(paperId);
        return next;
      });
    }
  }

  return (
    <div className="inner-page">
      <div className="brutalist-container">

        {/* ── Page Header ──────────────────────────────────────────────── */}
        <header className="page-header">
          <div className="page-header-left">
            <div className="page-counter">
              <span className="page-counter-num">01 / Library</span>
            </div>
            <h2 className="inner-h2">Research Library</h2>
            <p className="page-subtitle">
              Upload and manage academic publications to feed the agentic memory engine.
            </p>
          </div>
        </header>

        {error && (
          <ErrorBanner title="Ingestion Error" message={error.message} onDismiss={() => setError(null)} />
        )}

        {/* ── Two-Column Layout ─────────────────────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: "var(--space-md)", alignItems: "start" }}>

          {/* Left: Upload Controls */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>

            {/* Dropzone */}
            <div
              className="app-card app-card-cobalt"
              style={{
                padding: "var(--space-md)",
                textAlign: "center",
                border: dragging ? "2px solid var(--accent-cobalt)" : undefined,
                backgroundColor: dragging ? "var(--accent-cobalt-light)" : "var(--bg-card)",
                transition: "all 0.15s ease",
              }}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                handleFiles(e.dataTransfer.files);
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  justifyContent: "center",
                  alignItems: "center",
                  width: "44px",
                  height: "44px",
                  borderRadius: "50%",
                  backgroundColor: "var(--accent-cobalt-light)",
                  color: "var(--accent-cobalt)",
                  marginBottom: "var(--space-sm)",
                }}
              >
                {uploading ? <Loader2 size={20} className="icon-spin" /> : <UploadCloud size={20} />}
              </span>

              <h3 className="inner-h3" style={{ marginBottom: "6px" }}>
                {uploading ? "Ingesting PDF..." : "Upload PDF papers"}
              </h3>
              <p className="text-muted" style={{ marginBottom: "var(--space-sm)", fontSize: "0.82rem" }}>
                Drag and drop here, or browse your files.
              </p>

              <button
                type="button"
                className="brutalist-btn brutalist-btn-sm"
                disabled={uploading}
                onClick={() => inputRef.current?.click()}
              >
                Browse Files
              </button>
              <input
                ref={inputRef}
                type="file"
                accept="application/pdf"
                multiple
                hidden
                onChange={(e) => handleFiles(e.target.files)}
              />
            </div>

            {/* arXiv linker */}
            <div className="app-card" style={{ padding: "var(--space-md)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                <Link2 size={15} color="var(--accent-cobalt)" />
                <h3 className="inner-h3">Link from arXiv</h3>
              </div>
              <p className="text-muted" style={{ marginBottom: "var(--space-sm)", fontSize: "0.82rem" }}>
                Enter an arXiv ID (e.g. <code style={{ fontFamily: "var(--font-mono)", fontSize: "0.78rem", background: "#f0ede6", padding: "1px 5px", borderRadius: "3px" }}>2310.08560</code>) or a direct URL.
              </p>

              <form onSubmit={handleArxivSubmit} style={{ display: "flex", gap: "8px" }}>
                <input
                  type="text"
                  placeholder="2310.08560"
                  value={arxivValue}
                  onChange={(e) => setArxivValue(e.target.value)}
                  disabled={addingArxiv}
                  className="app-input"
                />
                <button
                  type="submit"
                  className="brutalist-btn brutalist-btn-primary brutalist-btn-sm"
                  disabled={addingArxiv || !arxivValue.trim()}
                  style={{ flexShrink: 0 }}
                >
                  {addingArxiv ? <Loader2 size={12} className="icon-spin" /> : "Link"}
                </button>
              </form>
            </div>

          </div>

          {/* Right: Paper List */}
          <div className="app-card" style={{ padding: "var(--space-md)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-sm)", paddingBottom: "var(--space-sm)", borderBottom: "1px solid var(--border-ui)" }}>
              <h3 className="inner-h3">Synchronized Manuscripts</h3>
              <span className="status-pill status-pill-neutral" style={{ fontSize: "0.7rem" }}>
                {papers.length} papers
              </span>
            </div>

            {loading ? (
              <p className="text-muted" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Loader2 size={13} className="icon-spin" /> Loading library...
              </p>
            ) : papers.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="Library empty"
                description="Ingest documents on the left to see them listed here."
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                {papers.map((paper) => (
                  <PaperRow
                    key={paper.id}
                    paper={paper}
                    onDelete={handleDelete}
                    deleting={deletingIds.has(paper.id)}
                  />
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
