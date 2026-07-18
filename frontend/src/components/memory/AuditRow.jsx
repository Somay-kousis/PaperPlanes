import { PlusCircle, RefreshCw, XCircle, Archive, Eye, Bot, User, Sparkles, Plug } from "lucide-react";
import MemoryDiffViewer from "./MemoryDiffViewer.jsx";
import { formatRelativeTime } from "../../lib/format.js";

const ACTION_CONFIG = {
  add: { Icon: PlusCircle, tone: "success" },
  update: { Icon: RefreshCw, tone: "info" },
  invalidate: { Icon: XCircle, tone: "danger" },
  archive: { Icon: Archive, tone: "warning" },
  read: { Icon: Eye, tone: "neutral" },
};

const ACTOR_ICON = {
  agent: Bot,
  user: User,
  reflection_worker: Sparkles,
  mcp: Plug,
};

/**
 * Single audit log entry. Reused both inside a note's own audit trail and in
 * the global audit feed tab (where `showTarget` reveals which note it hit).
 */
export default function AuditRow({ entry, showTarget = false, onOpenNote }) {
  const { Icon, tone } = ACTION_CONFIG[entry.action] ?? { Icon: RefreshCw, tone: "neutral" };
  const ActorIcon = ACTOR_ICON[entry.actor] ?? User;
  const before = entry.details?.before;
  const after = entry.details?.after;

  return (
    <div className="audit-row">
      <span className={`audit-icon audit-icon-${tone}`} aria-hidden="true">
        <Icon size={13} strokeWidth={2} />
      </span>
      <div className="audit-row-main">
        <div className="audit-row-top">
          <span className="audit-row-action">{entry.action}</span>
          <span className="audit-row-actor text-muted">
            <ActorIcon size={11} /> {entry.actor}
          </span>
          {showTarget && entry.target_id && (
            <button
              type="button"
              className="audit-target-link"
              onClick={() => onOpenNote?.(entry.target_id)}
            >
              note {String(entry.target_id).slice(0, 8)}
            </button>
          )}
          <span className="audit-row-time text-muted">{formatRelativeTime(entry.created_at)}</span>
        </div>
        {entry.reason && <div className="audit-row-reason text-muted">{entry.reason}</div>}
        {before && after && <MemoryDiffViewer before={before} after={after} />}
      </div>
    </div>
  );
}
