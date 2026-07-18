import { Trash2 } from "lucide-react";
import StatusBadge from "./StatusBadge.jsx";

function shortId(id) {
  return String(id ?? "").slice(0, 8);
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
}

function formatAuthors(authors) {
  if (!authors) return "";
  const list = Array.isArray(authors)
    ? authors
    : String(authors)
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean);
  if (list.length === 0) return "";
  if (list.length <= 2) return list.join(", ");
  return `${list.slice(0, 2).join(", ")} +${list.length - 2} more`;
}

export default function PaperRow({ paper, onDelete, deleting = false }) {
  const title = paper.title || `Untitled — ${shortId(paper.id)}`;
  const authors = formatAuthors(paper.authors);

  function handleDelete() {
    if (window.confirm(`Delete "${title}"? This cannot be undone.`)) {
      onDelete(paper.id);
    }
  }

  return (
    <div className="card paper-row" style={{ transition: "all var(--transition-base)", opacity: deleting ? 0.45 : 1, pointerEvents: deleting ? "none" : "auto" }}>
      <div className="paper-row-main">
        <strong className="paper-row-title">{title}</strong>
        {authors && <span className="paper-row-authors text-muted">{authors}</span>}
        <div className="paper-row-meta" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
          {paper.arxiv_id ? (
            <span className="tag-chip tag-chip-keyword" style={{ padding: "1px 6px", fontSize: "10px", margin: 0 }}>arXiv</span>
          ) : (
            <span className="tag-chip" style={{ padding: "1px 6px", fontSize: "10px", margin: 0 }}>PDF</span>
          )}
          <StatusBadge status={paper.status} failReason={paper.fail_reason} />
          {paper.status === "ready" && typeof paper.chunk_count === "number" && (
            <span className="text-muted">{paper.chunk_count} chunks</span>
          )}
          {paper.ingested_at && <span className="text-muted">{formatDate(paper.ingested_at)}</span>}
          {paper.arxiv_id && <span className="text-muted">ID: {paper.arxiv_id}</span>}
        </div>
        {paper.status === "failed" && paper.fail_reason && (
          <div className="paper-row-fail-reason">{paper.fail_reason}</div>
        )}
      </div>
      <button
        type="button"
        className="btn btn-icon paper-row-delete"
        onClick={handleDelete}
        disabled={deleting}
        aria-label={`Delete ${title}`}
        title="Delete paper"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}
