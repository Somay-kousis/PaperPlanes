import { CheckCircle2, Archive, XCircle, Link2 } from "lucide-react";
import use3dTilt from "../../lib/use3dTilt.js";

const TILES = [
  { key: "active", label: "Active notes", Icon: CheckCircle2, tone: "success" },
  { key: "archived", label: "Archived", Icon: Archive, tone: "neutral" },
  { key: "invalidated", label: "Invalidated", Icon: XCircle, tone: "danger" },
  { key: "links", label: "Links", Icon: Link2, tone: "info" },
];

export default function MemoryStatsHeader({ stats, loading }) {
  const notes = stats?.notes ?? {};
  const values = { ...notes, links: stats?.links ?? 0 };
  const last24h = stats?.audit_last_24h ?? {};
  const cardTilt = use3dTilt(6, 1.025);

  return (
    <div className="stats-header">
      <div className="stat-tiles">
        {TILES.map(({ key, label, Icon, tone }) => (
          <div
            className={`stat-tile stat-card-glowing stat-tile-${tone}`}
            key={key}
            onMouseMove={cardTilt.onMouseMove}
            onMouseLeave={cardTilt.onMouseLeave}
            onMouseEnter={cardTilt.onMouseEnter}
          >
            <span className="stat-tile-icon" aria-hidden="true">
              <Icon size={15} strokeWidth={2} />
            </span>
            <div>
              <div className="stat-tile-value">{loading ? "—" : (values[key] ?? 0)}</div>
              <div className="stat-tile-label">{label}</div>
            </div>
          </div>
        ))}
      </div>
      <div className="stats-subline text-muted">
        Last 24h — {last24h.add ?? 0} added · {last24h.update ?? 0} updated ·{" "}
        {last24h.invalidate ?? 0} invalidated · {last24h.read ?? 0} reads
      </div>
    </div>
  );
}
