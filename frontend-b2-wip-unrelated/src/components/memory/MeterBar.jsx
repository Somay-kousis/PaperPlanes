import { clamp01 } from "../../lib/format.js";

export default function MeterBar({ label, value, tone = "accent" }) {
  const pct = Math.round(clamp01(value) * 100);
  const colorMap = {
    accent: "var(--accent-cobalt)",
    info: "var(--accent-yellow)",
    red: "var(--accent-red)"
  };
  const fillColor = colorMap[tone] || "var(--accent-cobalt)";

  return (
    <div 
      style={{ 
        display: "flex", 
        alignItems: "center", 
        gap: "8px", 
        fontSize: "0.8rem",
        width: "100%"
      }} 
      title={`${label}: ${pct}%`}
    >
      <span className="mono text-muted" style={{ minWidth: "75px" }}>{label}</span>
      <span style={{ 
        flex: 1, 
        height: "5px", 
        backgroundColor: "var(--border-ui)", 
        borderRadius: "3px", 
        overflow: "hidden",
        display: "inline-block"
      }}>
        <span style={{ 
          display: "block",
          height: "100%", 
          width: `${pct}%`, 
          backgroundColor: fillColor,
          borderRadius: "3px"
        }} />
      </span>
      <span className="mono" style={{ minWidth: "35px", textAlign: "right", color: "var(--fg-navy)" }}>{pct}%</span>
    </div>
  );
}
