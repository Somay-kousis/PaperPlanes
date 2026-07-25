import { Trash2 } from "lucide-react";
import StatusBadge from "./StatusBadge.jsx";

function shortId(id) {
  return String(id ?? "").slice(0, 8);
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function formatAuthors(authors) {
  if (!authors) return "";
  const list = Array.isArray(authors)
    ? authors
    : String(authors).split(",").map((a) => a.trim()).filter(Boolean);
  if (list.length === 0) return "";
  if (list.length <= 2) return list.join(", ");
  return `${list.slice(0, 2).join(", ")} +${list.length - 2} more`;
}

export default function PaperRow({ paper, onDelete, deleting = false }) {
  const title = paper.title || `Untitled — ${shortId(paper.id)}`;
  const authors = formatAuthors(paper.authors);

  function handleDelete() {
    if (window.confirm(`Delete "${title}"? This cannot be undone.`)) onDelete(paper.id);
  }

  return (
    <div
      className="app-card"
      style={{
        padding: "var(--space-sm)",
        opacity: deleting ? 0.5 : 1,
        pointerEvents: deleting ? "none" : "auto",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "var(--space-sm)",
      }}
    >
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "5px" }}>
        <strong className="serif" style={{ fontSize: "1.05rem", color: "var(--fg-navy)", fontWeight: 600 }}>
          {title}
        </strong>

        {authors && (
          <p className="serif text-muted" style={{ fontSize: "0.88rem", margin: 0 }}>
            By {authors}
          </p>
        )}

        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span className="status-pill status-pill-neutral">
            {paper.arxiv_id ? "arXiv" : "PDF"}
          </span>

          <StatusBadge status={paper.status} failReason={paper.fail_reason} />

          {paper.status === "ready" && typeof paper.chunk_count === "number" && (
            <span className="mono text-muted">{paper.chunk_count} chunks</span>
          )}
          {paper.ingested_at && (
            <span className="mono text-muted">{formatDate(paper.ingested_at)}</span>
          )}
          {paper.arxiv_id && (
            <span className="mono text-muted">ID: {paper.arxiv_id}</span>
          )}
        </div>

        {paper.status === "failed" && paper.fail_reason && (
          <div
            className="mono"
            style={{ color: "var(--accent-red)", fontSize: "0.78rem", marginTop: "2px" }}
          >
            {paper.fail_reason}
          </div>
        )}
      </div>

      <button
        type="button"
        style={{
          padding: "6px",
          border: "1px solid var(--border-ui)",
          borderRadius: "5px",
          background: "transparent",
          color: "var(--accent-red)",
          cursor: "pointer",
          transition: "background 0.15s ease",
          flexShrink: 0,
        }}
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
