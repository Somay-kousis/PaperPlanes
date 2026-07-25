import { Eye } from "lucide-react";
import StatusBadge from "../StatusBadge.jsx";
import MeterBar from "./MeterBar.jsx";
import ProvenanceIcon from "./ProvenanceIcon.jsx";
import { formatRelativeTime } from "../../lib/format.js";

export default function NoteRow({ note, selected, onClick }) {
  return (
    <button
      type="button"
      style={{
        padding: "var(--space-sm)",
        border: selected ? "1px solid var(--accent-cobalt)" : "1px solid var(--border-ui)",
        borderRadius: "5px",
        backgroundColor: selected ? "var(--accent-cobalt-light)" : "var(--bg-card)",
        textAlign: "left",
        width: "100%",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        outline: "none",
        transition: "border-color 0.15s ease, background 0.15s ease"
      }}
      onClick={onClick}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", width: "100%", gap: "var(--space-xs)" }}>
        <p className="serif" style={{ fontSize: "1rem", fontWeight: "600", color: "var(--fg-navy)", flex: 1, margin: 0 }}>
          {note.content}
        </p>
        <StatusBadge status={note.status} />
      </div>

      {note.tags && note.tags.length > 0 && (
        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
          {note.tags.map((tag) => (
            <span
              className="mono text-muted"
              key={tag}
              style={{
                fontSize: "0.68rem",
                padding: "2px 7px",
                borderRadius: "100px",
                border: "1px solid var(--border-ui)",
                backgroundColor: "var(--bg-cream)",
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "4px", width: "100%", marginTop: "4px" }}>
        <MeterBar label="Importance" value={note.importance} tone="accent" />
        <MeterBar label="Strength" value={note.strength} tone="info" />
      </div>

      <div className="mono text-muted" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", fontSize: "0.72rem", marginTop: "4px" }}>
        <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ProvenanceIcon isUserStated={note.is_user_stated} />
          <span style={{ display: "flex", alignItems: "center", gap: "2px" }}>
            <Eye size={12} /> {note.access_count ?? 0}
          </span>
        </span>
        <span>{formatRelativeTime(note.created_at)}</span>
      </div>
    </button>
  );
}
