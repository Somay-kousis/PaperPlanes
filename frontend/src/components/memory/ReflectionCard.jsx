import { Sparkles } from "lucide-react";
import MeterBar from "./MeterBar.jsx";
import { formatRelativeTime } from "../../lib/format.js";

const TRIGGER_LABELS = {
  manual: "Manual",
  scheduled: "Scheduled",
  importance_threshold: "Importance threshold",
};

export default function ReflectionCard({ reflection, unavailableCiteIds, onOpenCite }) {
  const cites = reflection.cites ?? [];

  return (
    <div className="app-card" style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column", gap: "10px" }}>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {/* Trigger badge */}
        <span
          className="status-pill status-pill-cobalt"
          style={{ gap: "5px" }}
        >
          <Sparkles size={11} />
          {TRIGGER_LABELS[reflection.trigger_reason] ?? reflection.trigger_reason}
        </span>
        <span className="mono text-muted" style={{ fontSize: "0.72rem" }}>
          {formatRelativeTime(reflection.created_at)}
        </span>
      </div>

      <p className="serif" style={{ fontSize: "0.95rem", color: "var(--fg-navy)", margin: 0, lineHeight: 1.55 }}>
        {reflection.content}
      </p>

      <MeterBar label="Importance" value={reflection.importance} tone="accent" />

      {cites.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          <span className="mono text-muted" style={{ fontSize: "0.72rem" }}>
            Cites {cites.length} {cites.length === 1 ? "memory" : "memories"}
          </span>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {cites.map((id) => {
              const unavailable = unavailableCiteIds?.has(id);
              return (
                <button
                  key={id}
                  type="button"
                  className="mono"
                  style={{
                    padding: "2px 8px",
                    border: "1px solid var(--border-ui)",
                    borderRadius: "100px",
                    backgroundColor: unavailable ? "var(--bg-cream)" : "var(--accent-cobalt-light)",
                    color: unavailable ? "var(--fg-muted)" : "var(--accent-cobalt)",
                    cursor: unavailable ? "default" : "pointer",
                    fontSize: "0.7rem",
                    textDecoration: unavailable ? "line-through" : "none",
                  }}
                  onClick={() => onOpenCite?.(id)}
                  disabled={unavailable}
                  title={unavailable ? "Note is archived or no longer available" : undefined}
                >
                  note {String(id).slice(0, 8)}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
