function stringifyValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function MemoryDiffViewer({ before, after }) {
  if (!before || !after) return null;

  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).filter(
    (key) => stringifyValue(before[key]) !== stringifyValue(after[key]),
  );

  if (keys.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "6px" }} className="mono">
      {keys.map((key) => {
        const oldValue = stringifyValue(before[key]);
        const newValue = stringifyValue(after[key]);
        
        if (key === "content") {
          return (
            <div key={key} style={{ display: "flex", flexDirection: "column", gap: "4px", borderLeft: "2px solid var(--border-ui)", paddingLeft: "8px", margin: "4px 0" }}>
              <div className="mono text-muted" style={{ fontSize: "0.7rem" }}>content change:</div>
              <div style={{ fontSize: "0.8rem", color: "var(--accent-red)", textDecoration: "line-through" }} className="serif">"{oldValue}"</div>
              <div style={{ fontSize: "0.82rem", color: "var(--accent-green)" }} className="serif">"{newValue}"</div>
            </div>
          );
        }
        
        return (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.72rem" }}>
            <span className="text-muted" style={{ fontWeight: "bold" }}>{key}:</span>
            <span style={{ color: "var(--accent-red)", textDecoration: "line-through" }}>{oldValue}</span>
            <span className="text-muted">→</span>
            <span style={{ color: "var(--accent-green)" }}>{newValue}</span>
          </div>
        );
      })}
    </div>
  );
}
