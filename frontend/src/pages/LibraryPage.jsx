import { useCallback, useEffect, useRef, useState } from "react";
import { UploadCloud, FileText, Link2, Loader2 } from "lucide-react";

import { listPapers, uploadPaper, addArxivPaper, deletePaper } from "../lib/api.js";
import { isTerminalStatus } from "../components/StatusBadge.jsx";
import PaperRow from "../components/PaperRow.jsx";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import use3dTilt from "../lib/use3dTilt.js";

const POLL_INTERVAL_MS = 2500;

export default function LibraryPage() {
  const dropzoneTilt = use3dTilt(4, 1.015);
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

  const loadPapers = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const data = await listPapers();
      setPapers(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Poll while any paper is still in a non-terminal status; stop once
  // everything has settled into ready/failed. Only one timeout is ever
  // in flight at a time (tracked via pollTimeoutRef).
  const scheduleNextPoll = useCallback(
    (items) => {
      if (pollTimeoutRef.current) return;
      const hasInProgress = (items ?? []).some((paper) => !isTerminalStatus(paper.status));
      if (!hasInProgress) return;
      pollTimeoutRef.current = setTimeout(async () => {
        pollTimeoutRef.current = null;
        const data = await loadPapers({ silent: true });
        scheduleNextPoll(data);
      }, POLL_INTERVAL_MS);
    },
    [loadPapers],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const data = await loadPapers();
      if (!cancelled) scheduleNextPoll(data);
    })();
    return () => {
      cancelled = true;
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
      for (const file of files) {
        await uploadPaper(file);
      }
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
      setPapers((prev) => prev.filter((paper) => paper.id !== paperId));
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
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Library</h1>
          <p className="page-subtitle">Upload papers for PaperPlanes to read and remember.</p>
        </div>
      </div>

      {error && (
        <ErrorBanner
          title="Could not reach the backend"
          message={error.message}
          onDismiss={() => setError(null)}
        />
      )}

      <div
        className={"dropzone" + (dragging ? " dragging active-drag" : "")}
        onMouseMove={dropzoneTilt.onMouseMove}
        onMouseLeave={dropzoneTilt.onMouseLeave}
        onMouseEnter={dropzoneTilt.onMouseEnter}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
      >
        <span className="dropzone-icon">
          <UploadCloud size={20} strokeWidth={1.75} />
        </span>
        <h3>
          {uploading ? (
            <span className="flex-row" style={{ justifyContent: "center" }}>
              <Loader2 size={16} className="icon-spin" /> Ingesting research papers…
            </span>
          ) : (
            "Drag & drop PDFs here"
          )}
        </h3>
        <p className="text-muted">or</p>
        <button
          type="button"
          className="btn"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          hidden
          onChange={(event) => handleFiles(event.target.files)}
        />
      </div>

      <form className="arxiv-row" onSubmit={handleArxivSubmit}>
        <span className="arxiv-row-icon" aria-hidden="true">
          <Link2 size={15} />
        </span>
        <input
          type="text"
          className="input"
          placeholder="Add from arXiv — paste an ID (2310.08560) or URL"
          value={arxivValue}
          onChange={(event) => setArxivValue(event.target.value)}
          disabled={addingArxiv}
        />
        <button type="submit" className="btn btn-primary" disabled={addingArxiv || !arxivValue.trim()}>
          {addingArxiv ? <Loader2 size={14} className="icon-spin" /> : "Add"}
        </button>
      </form>

      {loading ? (
        <p className="text-muted">Loading library…</p>
      ) : papers.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No papers yet"
          description="Papers you upload will show up here with parsing status and extracted memory notes."
        />
      ) : (
        <div className="card-list">
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
  );
}
