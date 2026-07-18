import { useState } from "react";
import { History, Calendar, CornerDownRight, Activity } from "lucide-react";

const TIMELINE_DATA = {
  2024: {
    year: "2024",
    title: "Alcubierre Ingestion Influx",
    description: "Initial core physics claims ingested. First memory note generated and linked to Alcubierre's math models.",
    metrics: { latency: 8, vectors: 4, connections: 2, footprint: 4.8, conflicts: 0 },
    notes: [
      { id: "Note-01", content: "Warp bubble expansion requires negative energy density.", status: "ACTIVE", type: "active" }
    ]
  },
  2025: {
    year: "2025",
    title: "Hawking Quantum Ingestion",
    description: "Hawking's paper on transient energy states is processed. Vector ANN search determines no conflict; fact is appended.",
    metrics: { latency: 14, vectors: 10, connections: 3, footprint: 11.2, conflicts: 0 },
    notes: [
      { id: "Note-01", content: "Warp bubble expansion requires negative energy density.", status: "ACTIVE", type: "active" },
      { id: "Note-02", content: "Negative energy states are transient and local.", status: "ACTIVE", type: "active" }
    ]
  },
  2026: {
    year: "2026",
    title: "Casimir Invalidation Sweep",
    description: "White (2026) claims negative energy is sustainable. System triggers invalidation on Note-02. Note-02 valid_at is closed, Note-03 created.",
    metrics: { latency: 24, vectors: 13, connections: 5, footprint: 14.5, conflicts: 1 },
    notes: [
      { id: "Note-01", content: "Warp bubble expansion requires negative energy density.", status: "ACTIVE", type: "active" },
      { id: "Note-02", content: "Negative energy states are transient and local.", status: "INVALIDATED", type: "invalidated" },
      { id: "Note-03", content: "Negative energy density can be sustained indefinitely via Casimir fields.", status: "ACTIVE", type: "active" }
    ]
  }
};

export default function TimeTravelSlider() {
  const [selectedYear, setSelectedYear] = useState(2025);

  const activeData = TIMELINE_DATA[selectedYear];

  return (
    <div className="section-wrapper" style={{ backgroundColor: "transparent", borderBottom: "var(--border-thick)" }}>
      <div className="brutalist-container">
        
        {/* Header */}
        <div style={{ borderBottom: "var(--border-thick)", paddingBottom: "var(--space-sm)", marginBottom: "var(--space-lg)" }}>
          <div style={{ display: "flex", gap: "var(--space-xs)", alignItems: "center", marginBottom: "var(--space-xs)" }}>
            <span className="badge badge-yellow">TIMELINE_AS_OF // 03</span>
            <span className="mono" style={{ fontSize: "0.75rem", color: "var(--fg-navy)" }}>SCHEMA: BI-TEMPORAL</span>
          </div>
          <h2>As-Of Time Travel Simulator</h2>
          <p style={{ marginTop: "var(--space-sm)", color: "var(--fg-navy)", fontSize: "1.2rem", maxWidth: "800px" }}>
            Bi-temporal facts are never deleted. Use the slider below to query the CockroachDB engine at past points in transaction time.
          </p>
        </div>

        {/* Timeline Slider Control */}
        <div className="brutalist-block corner-cross bottom-cross" style={{ padding: "var(--space-md)", marginBottom: "var(--space-lg)", backgroundColor: "var(--bg-cream)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-sm)" }}>
            <span className="mono" style={{ fontWeight: "800" }}>Drag Timeline Handle:</span>
            <span className="badge badge-cobalt" style={{ fontSize: "1.1rem" }}>
              <Calendar size={14} style={{ display: "inline-block", marginRight: "6px", verticalAlign: "middle" }} />
              Year {selectedYear}
            </span>
          </div>

          <div style={{ position: "relative", padding: "10px 0" }}>
            <input 
              type="range" 
              min="2024" 
              max="2026" 
              step="1"
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              style={{
                width: "100%",
                height: "10px",
                backgroundColor: "var(--fg-navy)",
                outline: "none",
                cursor: "pointer",
                appearance: "none",
                borderRadius: "0px",
                border: "var(--border-thin)"
              }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "var(--space-xs)" }} className="mono">
              <span style={{ fontWeight: selectedYear === 2024 ? "bold" : "normal" }}>[ 2024.INIT ]</span>
              <span style={{ fontWeight: selectedYear === 2025 ? "bold" : "normal" }}>[ 2025.UPDATE ]</span>
              <span style={{ fontWeight: selectedYear === 2026 ? "bold" : "normal" }}>[ 2026.RECONCILE ]</span>
            </div>
          </div>
        </div>

        {/* Dynamic Timeline Result Grid */}
        <div className="b-grid-2">
          
          {/* Left: Events and Live Telemetry */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <div>
              <div className="mono" style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--accent-cobalt)", fontWeight: "bold", marginBottom: "var(--space-xs)" }}>
                <History size={16} /> TRANSACTION EVENT
              </div>
              <h3 style={{ textTransform: "none", fontSize: "1.8rem", marginBottom: "var(--space-xs)" }}>
                {activeData.title}
              </h3>
              <p style={{ fontSize: "1.05rem", lineHeight: 1.5, color: "var(--fg-navy)", opacity: 0.9 }}>
                {activeData.description}
              </p>
            </div>

            {/* Live Telemetry Panel */}
            <div className="brutalist-block" style={{ padding: "var(--space-sm)", backgroundColor: "var(--fg-navy)", color: "#a4acc2" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px", borderBottom: "1px solid rgba(164, 172, 194, 0.15)", paddingBottom: "4px", marginBottom: "var(--space-xs)" }}>
                <Activity size={14} style={{ color: "var(--accent-yellow)" }} />
                <span className="mono" style={{ fontSize: "0.7rem", color: "#ffffff", fontWeight: "bold" }}>TELEMETRY_GAUGE // LIVE_STATS</span>
              </div>
              
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }} className="mono">
                <div style={{ fontSize: "0.75rem" }}>
                  DB_CONNECTIONS: <strong style={{ color: "#ffffff" }}>{activeData.metrics.connections}</strong>
                </div>
                <div style={{ fontSize: "0.75rem" }}>
                  VECTORS_INDEXED: <strong style={{ color: "#ffffff" }}>{activeData.metrics.vectors}</strong>
                </div>
                <div style={{ fontSize: "0.75rem" }}>
                  SEARCH_LATENCY: <strong style={{ color: "var(--accent-green)" }}>{activeData.metrics.latency}ms</strong>
                </div>
                <div style={{ fontSize: "0.75rem" }}>
                  ACTIVE_CONFLICTS: <strong style={{ color: activeData.metrics.conflicts > 0 ? "var(--accent-red)" : "#ffffff" }}>{activeData.metrics.conflicts}</strong>
                </div>
              </div>
            </div>

            {/* Code query snippet */}
            <div>
              <span className="mono" style={{ fontSize: "0.7rem", color: "var(--accent-red)", fontWeight: "bold" }}>DB Query:</span>
              <div 
                className="mono" 
                style={{ 
                  backgroundColor: "var(--fg-navy)", 
                  color: "#ffffff", 
                  padding: "10px", 
                  fontSize: "0.75rem",
                  border: "var(--border-thin)",
                  boxShadow: "var(--shadow-flat-sm)"
                }}
              >
                SELECT * FROM memory_notes AS OF SYSTEM TIME '202{selectedYear - 2020}-07-18T12:00:00Z';
              </div>
            </div>
          </div>

          {/* Right: Active Memory belief states */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
            <h4 className="mono" style={{ borderBottom: "var(--border-thin)", paddingBottom: "4px" }}>
              Active Database Beliefs
            </h4>

            {activeData.notes.map((note) => {
              const isInvalid = note.status === "INVALIDATED";
              return (
                <div 
                  key={note.id}
                  className="brutalist-block"
                  style={{
                    padding: "var(--space-sm)",
                    backgroundColor: isInvalid ? "#fff7f6" : "#ffffff",
                    borderColor: isInvalid ? "var(--accent-red)" : "var(--fg-navy)",
                    opacity: isInvalid ? 0.85 : 1
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-xs)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <CornerDownRight size={14} />
                      <span className="mono" style={{ fontWeight: "700", fontSize: "0.8rem" }}>{note.id}</span>
                    </div>
                    <span className={`badge ${isInvalid ? 'badge-red' : 'badge-cobalt'}`} style={{ fontSize: "0.65rem", padding: "1px 5px" }}>
                      {note.status}
                    </span>
                  </div>
                  <p className="serif" style={{ fontSize: "1.1rem", fontWeight: "600", color: "var(--fg-navy)", textDecoration: isInvalid ? "line-through" : "none" }}>
                    "{note.content}"
                  </p>
                </div>
              );
            })}
          </div>

        </div>

      </div>
    </div>
  );
}
