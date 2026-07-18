import { History, X } from "lucide-react";
import { formatDateTime } from "../../lib/format.js";

export default function TimeTravelBanner({ asOf, onClear }) {
  if (!asOf) return null;
  
  return (
    <div 
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "10px 14px",
        border: "1px solid var(--accent-yellow)",
        backgroundColor: "var(--accent-yellow-light)",
        borderRadius: "5px",
        color: "var(--fg-navy)",
        fontSize: "0.88rem",
        marginBottom: "var(--space-md)"
      }}
      role="status"
    >
      <History size={15} strokeWidth={2} style={{ color: "var(--accent-yellow)", flexShrink: 0 }} />
      <span style={{ flex: 1 }}>
        Time-travel active: <strong>{formatDateTime(asOf)}</strong> — displaying the agent's belief states at this snapshot.
      </span>
      <button
        type="button"
        style={{
          border: "none",
          background: "transparent",
          cursor: "pointer",
          padding: "4px",
          color: "var(--fg-muted)"
        }}
        onClick={onClear}
        aria-label="Return to now"
        title="Return to now"
      >
        <X size={15} />
      </button>
    </div>
  );
}
