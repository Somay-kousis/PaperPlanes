import { AlertTriangle, X } from "lucide-react";

export default function ErrorBanner({ title, message, onDismiss }) {
  return (
    <div
      style={{
        padding: "var(--space-sm)",
        border: "1px solid var(--accent-red)",
        borderLeft: "4px solid var(--accent-red)",
        backgroundColor: "var(--accent-red-light)",
        borderRadius: "5px",
        marginBottom: "var(--space-md)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "var(--space-sm)",
      }}
    >
      <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "flex-start" }}>
        <AlertTriangle size={18} style={{ color: "var(--accent-red)", flexShrink: 0, marginTop: "2px" }} />
        <div>
          <div style={{ color: "var(--accent-red)", fontSize: "0.9rem", fontWeight: 700, marginBottom: "2px" }}>{title}</div>
          <p className="text-muted" style={{ fontSize: "0.85rem", lineHeight: 1.4 }}>{message}</p>
        </div>
      </div>
      {onDismiss && (
        <button
          style={{ padding: "4px", border: "none", background: "transparent", cursor: "pointer", color: "var(--fg-muted)", flexShrink: 0 }}
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X size={15} />
        </button>
      )}
    </div>
  );
}
