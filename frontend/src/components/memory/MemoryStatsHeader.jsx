import { CheckCircle2, Archive, XCircle, Link2 } from "lucide-react";

const TILES = [
  { key: "active", label: "Active Facts", Icon: CheckCircle2, color: "var(--accent-cobalt)" },
  { key: "archived", label: "Archived Facts", Icon: Archive, color: "#6c757d" },
  { key: "invalidated", label: "Invalidated Facts", Icon: XCircle, color: "var(--accent-red)" },
  { key: "links", label: "Semantic Links", Icon: Link2, color: "#a4acc2" },
];

export default function MemoryStatsHeader({ stats, loading }) {
  const notes = stats?.notes ?? {};
  const values = { ...notes, links: stats?.links ?? 0 };
  const last24h = stats?.audit_last_24h ?? {};

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "var(--space-md)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-sm)" }}>
        {TILES.map(({ key, label, Icon, color }) => (
          <div
            key={key}
            className="app-card"
            style={{
              padding: "var(--space-sm)",
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)"
            }}
          >
            <span style={{ 
              display: "inline-flex", 
              padding: "8px", 
              borderRadius: "50%", 
              backgroundColor: "var(--bg-cream)",
              color: color,
              flexShrink: 0
            }}>
              <Icon size={18} strokeWidth={2} />
            </span>
            <div>
              <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: "var(--fg-navy)", lineHeight: 1.1 }}>
                {loading ? "—" : (values[key] ?? 0)}
              </div>
              <div className="mono text-muted" style={{ marginTop: "2px" }}>
                {label}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mono text-muted" style={{ display: "flex", gap: "6px" }}>
        <span>Last 24h:</span>
        <span>{last24h.add ?? 0} added</span>
        <span>·</span>
        <span>{last24h.update ?? 0} updated</span>
        <span>·</span>
        <span>{last24h.invalidate ?? 0} invalidated</span>
        <span>·</span>
        <span>{last24h.read ?? 0} reads</span>
      </div>
    </div>
  );
}
