import { PlusCircle, RefreshCw, XCircle, Archive, Eye, Bot, User, Sparkles, Plug } from "lucide-react";
import MemoryDiffViewer from "./MemoryDiffViewer.jsx";
import { formatRelativeTime } from "../../lib/format.js";

const ACTION_CONFIG = {
  add: { Icon: PlusCircle, color: "var(--accent-green)" },
  update: { Icon: RefreshCw, color: "var(--accent-cobalt)" },
  invalidate: { Icon: XCircle, color: "var(--accent-red)" },
  archive: { Icon: Archive, color: "var(--accent-yellow)" },
  read: { Icon: Eye, color: "#6c757d" },
};

const ACTOR_ICON = {
  agent: Bot,
  user: User,
  reflection_worker: Sparkles,
  mcp: Plug,
};

export default function AuditRow({ entry, showTarget = false, onOpenNote }) {
  const { Icon, color } = ACTION_CONFIG[entry.action] ?? { Icon: RefreshCw, color: "var(--text-muted)" };
  const ActorIcon = ACTOR_ICON[entry.actor] ?? User;
  const before = entry.details?.before;
  const after = entry.details?.after;

  return (
    <div style={{ 
      display: "flex", 
      gap: "var(--space-xs)", 
      padding: "10px 0", 
      borderBottom: "1px solid var(--border-ui)",
      alignItems: "flex-start"
    }}>
      <span style={{ 
        display: "inline-flex", 
        padding: "4px", 
        borderRadius: "4px", 
        backgroundColor: "var(--bg-cream)",
        color: color,
        flexShrink: 0
      }}>
        <Icon size={14} strokeWidth={2} />
      </span>

      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "2px" }}>
        <div className="mono" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", fontSize: "0.72rem" }}>
          <span className="mono-upper" style={{ fontWeight: "bold", color: "var(--fg-navy)", fontSize: "0.65rem" }}>{entry.action}</span>
          
          <span className="text-muted" style={{ display: "inline-flex", alignItems: "center", gap: "3px", fontSize: "0.72rem" }}>
            <ActorIcon size={11} /> {entry.actor}
          </span>
          
          {showTarget && entry.target_id && (
            <button
              type="button"
              style={{
                border: "none",
                background: "transparent",
                color: "var(--accent-cobalt)",
                textDecoration: "underline",
                cursor: "pointer",
                padding: 0,
                fontSize: "0.75rem"
              }}
              onClick={() => onOpenNote?.(entry.target_id)}
            >
              note {String(entry.target_id).slice(0, 8)}
            </button>
          )}

          <span className="text-muted" style={{ marginLeft: "auto" }}>{formatRelativeTime(entry.created_at)}</span>
        </div>

        {entry.reason && (
          <div className="serif text-muted" style={{ fontSize: "0.85rem", marginTop: "2px" }}>
            Reason: {entry.reason}
          </div>
        )}

        {before && after && <MemoryDiffViewer before={before} after={after} />}
      </div>
    </div>
  );
}
