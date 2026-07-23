import { useState, useEffect, useRef } from "react";
import { FileText, Loader2, Play, AlertTriangle, CheckCircle, RefreshCw, Layers } from "lucide-react";

const MOCK_PAPERS = [
  {
    id: "paper-1",
    title: "The Physics of Warp Drives",
    authors: "M. Alcubierre",
    year: 2024,
    claim: "Warp bubble expansion requires negative energy density.",
    noteId: "Note-01",
    logs: [
      "[FETCH] Downloading PDF from S3 bucket: alcu-warp-2024.pdf",
      "[PARSE] Completed PDF parsing. 8,240 tokens extracted.",
      "[CHUNK] Created 4 chunks with 1024-dim Titan Text V2 vectors.",
      "[MEM_WRITE] Consolidated fact: 'Warp bubble expansion requires negative energy density.'",
      "[MEM_WRITE] Action: ADD -> New note created (ID: Note-01).",
      "[STATUS] Ingestion complete. Memory node active."
    ]
  },
  {
    id: "paper-2",
    title: "Quantum Vacuum Energy Dynamics",
    authors: "S. Hawking",
    year: 2025,
    claim: "Negative energy states are transient and local.",
    noteId: "Note-02",
    logs: [
      "[FETCH] Fetching manuscript from arXiv: 2501.04910",
      "[PARSE] Completed PDF parsing. 12,410 tokens extracted.",
      "[CHUNK] Created 6 chunks with 1024-dim Titan Text V2 vectors.",
      "[MEM_WRITE] Consolidated fact: 'Negative energy states are transient and local.'",
      "[MEM_WRITE] Action: ADD -> New note created (ID: Note-02).",
      "[STATUS] Ingestion complete. Memory node active."
    ]
  },
  {
    id: "paper-3",
    title: "Advanced Quantum Warp Mechanics",
    authors: "H. White",
    year: 2026,
    claim: "Negative energy density can be sustained indefinitely via Casimir fields.",
    noteId: "Note-03",
    logs: [
      "[FETCH] Downloading PDF from S3 bucket: white-casimir-2026.pdf",
      "[PARSE] Completed PDF parsing. 6,180 tokens extracted.",
      "[CHUNK] Created 3 chunks with 1024-dim Titan Text V2 vectors.",
      "[MEM_WRITE] Consolidated fact: 'Negative energy density can be sustained indefinitely via Casimir fields.'",
      "[DECISION] Similarity search match against Note-02 = 0.76. LLM query sent.",
      "[DECISION] Option selected: INVALIDATE (target: Note-02).",
      "[CONTRADICTION] Clashing claims found between Note-02 and Note-03!",
      "[STATUS] Ingestion complete. Contradiction flagged."
    ]
  }
];

export default function InteractiveSandbox() {
  const [fedPapers, setFedPapers] = useState([]);
  const [ingestingId, setIngestingId] = useState(null);
  const [logs, setLogs] = useState(["[SYSTEM] Memory engine online. Awaiting document feed..."]);
  const [selectedPaperId, setSelectedPaperId] = useState("paper-1");
  const [showContradiction, setShowContradiction] = useState(false);
  const [resolvedState, setResolvedState] = useState(null); // null | 'Superseded' | 'Complementary' | 'Outdated'
  const logEndRef = useRef(null);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollTop = logEndRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    const hasPaper2 = fedPapers.includes("paper-2");
    const hasPaper3 = fedPapers.includes("paper-3");
    if (hasPaper2 && hasPaper3) {
      setShowContradiction(true);
    } else {
      setShowContradiction(false);
    }
  }, [fedPapers]);

  const feedPaper = (paper) => {
    if (fedPapers.includes(paper.id) || ingestingId) return;

    setIngestingId(paper.id);
    setSelectedPaperId(paper.id);
    
    let logIndex = 0;
    setLogs(prev => [...prev, `[INGEST] Feeding paper: "${paper.title}"`]);

    const interval = setInterval(() => {
      if (logIndex < paper.logs.length) {
        setLogs(prev => [...prev, paper.logs[logIndex]]);
        logIndex++;
      } else {
        clearInterval(interval);
        setFedPapers(prev => [...prev, paper.id]);
        setIngestingId(null);
      }
    }, 600);
  };

  const resetSandbox = () => {
    setFedPapers([]);
    setIngestingId(null);
    setLogs(["[SYSTEM] Memory engine reset. Awaiting document feed..."]);
    setShowContradiction(false);
    setResolvedState(null);
  };

  return (
    <div className="section-wrapper grid-lines" style={{ borderBottom: "var(--border-thick)" }}>
      <div className="brutalist-container">
        
        {/* Header Block with Blueprint styling */}
        <div style={{ borderBottom: "var(--border-thick)", paddingBottom: "var(--space-md)", marginBottom: "var(--space-lg)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--space-sm)" }}>
            <div>
              <div style={{ display: "flex", gap: "var(--space-xs)", alignItems: "center", marginBottom: "var(--space-xs)" }}>
                <span className="badge badge-cobalt">INGESTION_SHELF // 02</span>
                <span className="mono" style={{ fontSize: "0.75rem", color: "var(--fg-navy)" }}>LOC: PP-LND-02</span>
              </div>
              <h2>Interactive RAG Simulator</h2>
            </div>
            <button 
              className="brutalist-btn brutalist-btn-red" 
              style={{ boxShadow: "var(--shadow-flat-sm)" }}
              onClick={resetSandbox}
            >
              <RefreshCw size={16} /> Reset Engine
            </button>
          </div>
          <p style={{ marginTop: "var(--space-sm)", color: "var(--fg-navy)", fontSize: "1.2rem", maxWidth: "800px" }}>
            Feed research documents to the engine. Observe vector ANN similarity thresholds, dynamic log triggers, and automated invalidation sweeps.
          </p>
        </div>

        {/* Dynamic Sandbox Workspace */}
        <div className="b-grid-2">
          
          {/* Left Column: Dossier Folders */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "var(--border-thin)", paddingBottom: "var(--space-xs)" }}>
              <h3 className="mono" style={{ fontSize: "1.1rem" }}>
                1. Input Dossiers
              </h3>
              <span className="mono" style={{ opacity: 0.6 }}>SYSTEM: STABLE</span>
            </div>

            {MOCK_PAPERS.map((paper) => {
              const isFed = fedPapers.includes(paper.id);
              const isIngesting = ingestingId === paper.id;
              const isSelected = selectedPaperId === paper.id;

              return (
                <div 
                  key={paper.id}
                  className="dossier-folder scanner-container corner-cross bottom-cross"
                  style={{ 
                    borderColor: isSelected ? "var(--accent-cobalt)" : "var(--fg-navy)",
                    backgroundColor: isSelected ? "#ffffff" : "#ffffff",
                    transform: isSelected ? "translate(-2px, -2px)" : "none",
                    boxShadow: isSelected ? "10px 10px 0px #101b3a" : "var(--shadow-flat)"
                  }}
                  onClick={() => setSelectedPaperId(paper.id)}
                >
                  {/* Dossier Tab Top Left */}
                  <span className={`dossier-tab ${isFed ? 'dossier-tab-cobalt' : ''}`}>
                    {paper.id.toUpperCase()}
                  </span>

                  {/* Scanning Laser Animation */}
                  {isIngesting && <div className="laser-line" />}

                  <div style={{ padding: "var(--space-sm)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "var(--space-xs)" }}>
                      <div style={{ display: "flex", gap: "var(--space-sm)" }}>
                        <FileText size={28} style={{ color: isSelected ? "var(--accent-cobalt)" : "var(--fg-navy)", flexShrink: 0, marginTop: "2px" }} />
                        <div>
                          <h4 style={{ fontSize: "1.1rem", textTransform: "none", letterSpacing: "-0.01em", color: "var(--fg-navy)" }}>
                            {paper.title}
                          </h4>
                          <p style={{ fontSize: "0.85rem", color: "var(--fg-navy)", opacity: 0.75, fontFamily: "'JetBrains Mono', monospace" }}>
                            BY {paper.authors.toUpperCase()} // INGEST_YEAR: {paper.year}
                          </p>
                        </div>
                      </div>
                      
                      {isFed ? (
                        <span className="badge badge-cobalt">INGESTED</span>
                      ) : isIngesting ? (
                        <span className="badge badge-yellow">
                          <Loader2 size={12} className="icon-spin" style={{ display: "inline-block", marginRight: "4px" }} /> INGESTING
                        </span>
                      ) : (
                        <button 
                          className="brutalist-btn"
                          style={{ padding: "6px 12px", fontSize: "0.8rem", boxShadow: "var(--shadow-flat-sm)" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            feedPaper(paper);
                          }}
                        >
                          <Play size={10} /> FEED
                        </button>
                      )}
                    </div>
                    
                    <div style={{ marginTop: "var(--space-sm)", borderTop: "var(--border-dashed)", paddingTop: "var(--space-sm)" }}>
                      <span className="mono" style={{ fontSize: "0.75rem", color: "var(--accent-cobalt)", fontWeight: "bold" }}>Ingestion Claim:</span>
                      <p className="serif" style={{ fontSize: "1.05rem", fontStyle: "italic", marginTop: "2px" }}>
                        "{paper.claim}"
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right Column: Schema Node & Console */}
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "var(--border-thin)", paddingBottom: "var(--space-xs)" }}>
              <h3 className="mono" style={{ fontSize: "1.1rem" }}>
                2. DB Introspection & Graph
              </h3>
              <span className="mono" style={{ opacity: 0.6 }}>AS_OF: LIVE</span>
            </div>

            {/* Visual SQL DB Graph */}
            <div 
              className="brutalist-block corner-cross bottom-cross"
              style={{ 
                height: "230px", 
                backgroundColor: "#ffffff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                overflow: "hidden"
              }}
            >
              {fedPapers.length === 0 && !ingestingId ? (
                <div style={{ textAlign: "center", padding: "var(--space-md)" }}>
                  <Layers size={36} style={{ color: "var(--accent-cobalt)", margin: "0 auto var(--space-xs) auto", animation: "pulse 2s infinite" }} />
                  <p className="mono" style={{ fontSize: "0.85rem", fontWeight: "700" }}>NO MEMORY ENTRIES IN COCKROACHDB</p>
                  <p style={{ fontSize: "0.85rem", opacity: 0.75 }}>Awaiting document vector feeds...</p>
                </div>
              ) : (
                <div style={{ display: "flex", width: "100%", height: "100%", position: "relative", alignItems: "center", justifyContent: "center", gap: "24px" }}>
                  
                  {/* Paper 1 SQL DB Node */}
                  {fedPapers.includes("paper-1") && (
                    <div 
                      className="brutalist-block"
                      style={{ 
                        width: "125px",
                        backgroundColor: "var(--bg-cream)", 
                        borderWidth: "2px", 
                        zIndex: 2,
                        boxShadow: "var(--shadow-flat-sm)",
                        fontSize: "0.7rem"
                      }}
                    >
                      <div style={{ backgroundColor: "var(--fg-navy)", color: "#ffffff", padding: "2px 6px", fontWeight: "bold" }} className="mono">
                        Note-01
                      </div>
                      <div style={{ padding: "4px", display: "flex", flexDirection: "column", gap: "2px" }} className="mono">
                        <div><strong>IMP:</strong> 0.85</div>
                        <div style={{ borderTop: "1px solid #101b3a" }}><strong>STAT:</strong> ACTIVE</div>
                        <div style={{ borderTop: "1px solid #101b3a", whiteSpace: "nowrap", overflow: "hidden" }}><strong>EXP:</strong> INF</div>
                      </div>
                    </div>
                  )}

                  {/* Paper 2 SQL DB Node */}
                  {fedPapers.includes("paper-2") && (
                    <div 
                      className="brutalist-block"
                      style={{ 
                        width: "125px",
                        backgroundColor: resolvedState ? "var(--bg-cream)" : showContradiction ? "#fff5f5" : "var(--bg-cream)",
                        borderColor: showContradiction && !resolvedState ? "var(--accent-red)" : "var(--fg-navy)",
                        borderWidth: "2px",
                        zIndex: 2,
                        boxShadow: showContradiction && !resolvedState ? "4px 4px 0px #ff3b30" : "var(--shadow-flat-sm)",
                        fontSize: "0.7rem"
                      }}
                    >
                      <div 
                        style={{ 
                          backgroundColor: showContradiction && !resolvedState ? "var(--accent-red)" : "var(--fg-navy)", 
                          color: "#ffffff", 
                          padding: "2px 6px", 
                          fontWeight: "bold",
                          display: "flex",
                          justifyContent: "space-between"
                        }} 
                        className="mono"
                      >
                        <span>Note-02</span>
                        {showContradiction && !resolvedState && <span>⚠️</span>}
                      </div>
                      <div style={{ padding: "4px", display: "flex", flexDirection: "column", gap: "2px" }} className="mono">
                        <div><strong>IMP:</strong> 0.72</div>
                        <div style={{ borderTop: "1px solid #101b3a" }}><strong>STAT:</strong> {resolvedState ? "INVALID" : showContradiction ? "DISPUTED" : "ACTIVE"}</div>
                        <div style={{ borderTop: "1px solid #101b3a", whiteSpace: "nowrap", overflow: "hidden" }}><strong>EXP:</strong> {resolvedState ? "2026_SYS" : "INF"}</div>
                      </div>
                    </div>
                  )}

                  {/* Connecting Vector Paths */}
                  {showContradiction && (
                    <div 
                      style={{ 
                        position: "absolute",
                        top: "50%",
                        left: "35%",
                        right: "35%",
                        height: "3px",
                        borderTop: resolvedState ? "3px dashed var(--accent-cobalt)" : "3px dashed var(--accent-red)",
                        transform: "translateY(-50%)",
                        zIndex: 1,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center"
                      }}
                    >
                      <span 
                        className="mono" 
                        style={{ 
                          fontSize: "0.6rem", 
                          backgroundColor: resolvedState ? "var(--accent-cobalt)" : "var(--accent-red)", 
                          color: "#ffffff", 
                          padding: "1px 5px", 
                          transform: "translateY(-2px)",
                          fontWeight: "bold"
                        }}
                      >
                        {resolvedState ? "RESOLVED" : "CLASH"}
                      </span>
                    </div>
                  )}

                  {/* Paper 3 SQL DB Node */}
                  {fedPapers.includes("paper-3") && (
                    <div 
                      className="brutalist-block"
                      style={{ 
                        width: "125px",
                        backgroundColor: resolvedState ? "var(--bg-cream)" : showContradiction ? "#fff5f5" : "var(--bg-cream)",
                        borderColor: showContradiction && !resolvedState ? "var(--accent-red)" : "var(--fg-navy)",
                        borderWidth: "2px",
                        zIndex: 2,
                        boxShadow: "var(--shadow-flat-sm)",
                        fontSize: "0.7rem"
                      }}
                    >
                      <div style={{ backgroundColor: "var(--fg-navy)", color: "#ffffff", padding: "2px 6px", fontWeight: "bold" }} className="mono">
                        Note-03
                      </div>
                      <div style={{ padding: "4px", display: "flex", flexDirection: "column", gap: "2px" }} className="mono">
                        <div><strong>IMP:</strong> 0.91</div>
                        <div style={{ borderTop: "1px solid #101b3a" }}><strong>STAT:</strong> ACTIVE</div>
                        <div style={{ borderTop: "1px solid #101b3a", whiteSpace: "nowrap", overflow: "hidden" }}><strong>EXP:</strong> INF</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Console Log Panel */}
            <div 
              className="brutalist-block"
              style={{ 
                height: "170px", 
                backgroundColor: "#101b3a", 
                color: "#a4acc2", 
                padding: "var(--space-sm)", 
                overflowY: "auto", 
                boxShadow: "var(--shadow-flat-sm)",
                display: "flex",
                flexDirection: "column",
                gap: "2px"
              }}
            >
              {/* Terminal Header Action Lights */}
              <div style={{ display: "flex", gap: "6px", marginBottom: "var(--space-xs)", borderBottom: "1px solid rgba(164, 172, 194, 0.15)", paddingBottom: "4px" }}>
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "var(--accent-red)" }} />
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "var(--accent-yellow)" }} />
                <span style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "var(--accent-green)" }} />
                <span className="mono" style={{ fontSize: "0.65rem", marginLeft: "auto", color: "rgba(164, 172, 194, 0.6)" }}>INGEST_LOGGER // V2.0</span>
              </div>

              <div ref={logEndRef} style={{ overflowY: "auto", flex: 1 }}>
                {logs.map((log, index) => {
                  let color = "#a4acc2";
                  if (log.startsWith("[SYSTEM]")) color = "var(--accent-yellow)";
                  if (log.startsWith("[INGEST]")) color = "#ffffff";
                  if (log.startsWith("[MEM_WRITE]")) color = "#00cc66";
                  if (log.startsWith("[DECISION]")) color = "#ffd300";
                  if (log.startsWith("[CONTRADICTION]")) color = "var(--accent-red)";
                  
                  return (
                    <div key={index} className="mono" style={{ color, fontSize: "0.75rem", lineHeight: 1.4, wordBreak: "break-all" }}>
                      {log}
                    </div>
                  );
                })}
              </div>
            </div>

          </div>
        </div>

        {/* Contradiction Clashing Warning & Form */}
        {showContradiction && (
          <div 
            className="brutalist-block"
            style={{ 
              marginTop: "var(--space-lg)", 
              padding: "var(--space-md)", 
              borderColor: resolvedState ? "var(--accent-cobalt)" : "var(--accent-red)",
              backgroundColor: resolvedState ? "#f4f8ff" : "#fff6f5",
              boxShadow: resolvedState ? "var(--shadow-flat-blue)" : "8px 8px 0px #ff3b30",
              animation: resolvedState ? "none" : "shake 0.3s ease-in-out"
            }}
          >
            <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "flex-start" }}>
              {resolvedState ? (
                <CheckCircle size={32} style={{ color: "var(--accent-cobalt)", flexShrink: 0, marginTop: "2px" }} />
              ) : (
                <AlertTriangle size={32} style={{ color: "var(--accent-red)", flexShrink: 0, marginTop: "2px" }} />
              )}
              <div style={{ flex: 1 }}>
                <h3 style={{ fontSize: "1.25rem", color: resolvedState ? "var(--accent-cobalt)" : "var(--accent-red)", marginBottom: "var(--space-xs)" }}>
                  {resolvedState ? `RESOLVED // CLAIMS RECONCILED` : "CONFLICTING FACTS INGESTED"}
                </h3>
                
                <p className="serif" style={{ fontSize: "1.1rem", fontWeight: "600", marginBottom: "var(--space-sm)", color: "var(--fg-navy)" }}>
                  Hawking (2025) claims negative energy states are strictly <span style={{ textDecoration: "underline" }}>transient</span>, while White (2026) asserts they can be <span style={{ textDecoration: "underline" }}>sustained indefinitely</span> using Casimir fields.
                </p>

                {resolvedState ? (
                  <p style={{ fontSize: "0.95rem", fontStyle: "italic", fontFamily: "'JetBrains Mono', monospace" }}>
                    LOG: Reconciled under strategy [{resolvedState.toUpperCase()}]. Closed valid_at timeline on Note-02 system-wide.
                  </p>
                ) : (
                  <div>
                    <p style={{ fontSize: "0.8rem", marginBottom: "var(--space-xs)", textTransform: "uppercase", fontWeight: "bold" }} className="mono">
                      Execute Resolution Strategy:
                    </p>
                    <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
                      <button 
                        className="brutalist-btn brutalist-btn-primary"
                        style={{ padding: "8px 16px", fontSize: "0.85rem" }}
                        onClick={() => setResolvedState("Superseded")}
                      >
                        Supersede Hawking
                      </button>
                      <button 
                        className="brutalist-btn"
                        style={{ padding: "8px 16px", fontSize: "0.85rem" }}
                        onClick={() => setResolvedState("Complementary")}
                      >
                        Complementary (Both Active)
                      </button>
                      <button 
                        className="brutalist-btn"
                        style={{ padding: "8px 16px", fontSize: "0.85rem" }}
                        onClick={() => setResolvedState("Outdated")}
                      >
                        Flag Hawking Outdated
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
