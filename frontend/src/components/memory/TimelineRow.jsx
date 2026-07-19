import { formatDateTime } from "../../lib/format.js";

export default function TimelineRow({ label, startLabel, startIso, endLabel, endIso }) {
  const ongoing = !endIso;
  return (
    <div style={{ marginBottom: "12px" }}>
      <div className="mono text-muted" style={{ fontSize: "0.72rem", marginBottom: "4px" }}>{label}</div>
      
      <div style={{ display: "flex", alignItems: "center", gap: "6px", height: "10px", margin: "4px 0" }}>
        <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "var(--fg-navy)" }} />
        <span style={{ 
          flex: 1, 
          height: "2px", 
          backgroundImage: ongoing ? "repeating-linear-gradient(90deg, var(--fg-navy), var(--fg-navy) 4px, transparent 4px, transparent 8px)" : "none",
          backgroundColor: ongoing ? "transparent" : "var(--fg-navy)" 
        }} />
        <span style={{ 
          width: "6px", 
          height: "6px", 
          borderRadius: "50%", 
          border: "1px solid var(--fg-navy)",
          backgroundColor: ongoing ? "transparent" : "var(--fg-navy)" 
        }} />
      </div>

      <div className="mono text-muted" style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem" }}>
        <span>{startLabel}: {formatDateTime(startIso) || "—"}</span>
        <span>{ongoing ? `${endLabel}: ongoing` : `${endLabel}: ${formatDateTime(endIso)}`}</span>
      </div>
    </div>
  );
}
