import { ArrowRight, ArrowUpRight } from "lucide-react";
import InteractiveSandbox from "../components/InteractiveSandbox.jsx";
import TimeTravelSlider from "../components/TimeTravelSlider.jsx";
import { Link } from "react-router";

export default function LandingPage() {
  return (
    <div className="landing-page">
      {/* Hero Section */}
      <header className="section-wrapper" style={{ backgroundColor: "transparent" }}>
        <div className="brutalist-container">
          <div className="b-grid-2" style={{ alignItems: "center", gap: "40px" }}>
            
            <div>
              <div style={{ display: "flex", gap: "var(--space-xs)", alignItems: "center", marginBottom: "var(--space-sm)" }}>
                <span className="badge badge-yellow">SYS_OVERVIEW // 01</span>
                <span className="mono" style={{ fontSize: "0.75rem" }}>LOC: PP-LND-01</span>
              </div>
              <h1 style={{ marginBottom: "var(--space-sm)" }}>
                THE MEMORY LAYER THAT REMEMBERS.
              </h1>
              <p style={{ fontSize: "1.3rem", fontWeight: "600", lineHeight: 1.4, marginBottom: "var(--space-md)", color: "var(--fg-navy)" }}>
                Most agent memories are vectors bolted onto static chat logs. PaperPlanes builds a unified memory architecture on CockroachDB to index claims, detect contradictions, and support time-travel query states.
              </p>
              
              <div style={{ display: "flex", gap: "var(--space-sm)", flexWrap: "wrap" }}>
                <button 
                  className="brutalist-btn brutalist-btn-primary"
                  onClick={() => document.getElementById("sandbox").scrollIntoView({ behavior: "smooth" })}
                >
                  Start Sandbox <ArrowRight size={16} />
                </button>
                <Link 
                  to="/library" 
                  className="brutalist-btn"
                >
                  Enter Real Library <ArrowUpRight size={16} />
                </Link>
              </div>
            </div>

            <div style={{ position: "relative" }}>
              <div className="ink-image-wrapper" style={{ transform: "rotate(-1.5deg)" }}>
                <img 
                  src="https://images.unsplash.com/photo-1518005020951-eccb494ad742?auto=format&fit=crop&w=800&q=80" 
                  alt="Brutalist architectural concrete structures"
                  className="ink-image"
                  style={{ height: "380px", objectFit: "cover" }}
                />
              </div>
              <div 
                className="mono" 
                style={{ 
                  position: "absolute", 
                  bottom: "-15px", 
                  left: "15px", 
                  backgroundColor: "var(--accent-yellow)", 
                  padding: "4px 12px", 
                  border: "var(--border-thin)",
                  fontWeight: "bold",
                  fontSize: "0.75rem"
                }}
              >
                INGESTION_NODE // SPIRAL_STRUCT
              </div>
            </div>

          </div>
        </div>
      </header>

      {/* Sandbox Section */}
      <section id="sandbox">
        <InteractiveSandbox />
      </section>

      {/* Core Features Grid */}
      <section id="features" className="section-wrapper" style={{ backgroundColor: "transparent" }}>
        
        <div style={{ position: "absolute", left: "20px", top: "100px", display: "none", md: "block" }}>
          <div className="vertical-label">SPECIFICATIONS // LAYER_INFO</div>
        </div>

        <div className="brutalist-container">
          
          <div style={{ borderBottom: "var(--border-thick)", paddingBottom: "var(--space-md)", marginBottom: "var(--space-lg)" }}>
            <div style={{ display: "flex", gap: "var(--space-xs)", alignItems: "center", marginBottom: "var(--space-xs)" }}>
              <span className="badge badge-cobalt">SYS_SPEC // 03</span>
              <span className="mono" style={{ fontSize: "0.75rem" }}>LOC: PP-LND-03</span>
            </div>
            <h2>Technical Specifications</h2>
            <p style={{ marginTop: "var(--space-xs)", color: "var(--fg-navy)", fontSize: "1.2rem", maxWidth: "600px" }}>
              Four layers of memory, fully implemented in a single, resilient CockroachDB database cluster.
            </p>
          </div>

          <div className="b-grid-2" style={{ gap: "40px", alignItems: "center" }}>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
              
              <div className="brutalist-block" style={{ padding: "var(--space-sm)" }}>
                <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "flex-start" }}>
                  <div style={{ backgroundColor: "var(--accent-cobalt)", color: "#ffffff", padding: "10px", border: "var(--border-thin)" }}>
                    <ArrowRight size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "1.15rem", marginBottom: "4px", textTransform: "none" }}>Bi-Temporal Fact Tables</h3>
                    <p style={{ fontSize: "0.95rem", color: "var(--fg-navy)" }}>
                      Claims record event timelines (<code>valid_at</code>/<code>invalid_at</code>) and transaction timelines. Facts are closed out, never deleted.
                    </p>
                  </div>
                </div>
              </div>

              <div className="brutalist-block" style={{ padding: "var(--space-sm)", transform: "rotate(0.5deg)" }}>
                <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "flex-start" }}>
                  <div style={{ backgroundColor: "var(--accent-yellow)", color: "var(--fg-navy)", padding: "10px", border: "var(--border-thin)" }}>
                    <ArrowRight size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "1.15rem", marginBottom: "4px", textTransform: "none" }}>Cloud-Managed MCP Introspection</h3>
                    <p style={{ fontSize: "0.95rem", color: "var(--fg-navy)" }}>
                      The chat agent discovers schemas and reads its own memory tables dynamically via a secure, read-only Model Context Protocol server.
                    </p>
                  </div>
                </div>
              </div>

              <div className="brutalist-block" style={{ padding: "var(--space-sm)", transform: "rotate(-0.5deg)" }}>
                <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "flex-start" }}>
                  <div style={{ backgroundColor: "var(--accent-red)", color: "#ffffff", padding: "10px", border: "var(--border-thin)" }}>
                    <ArrowRight size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "1.15rem", marginBottom: "4px", textTransform: "none" }}>Contradiction Judgement</h3>
                    <p style={{ fontSize: "0.95rem", color: "var(--fg-navy)" }}>
                      Titan-embedded claims are vector-matched against active assertions. Any clash triggers a dispute node, requiring manual or automated resolution.
                    </p>
                  </div>
                </div>
              </div>

              <div className="brutalist-block" style={{ padding: "var(--space-sm)" }}>
                <div style={{ display: "flex", gap: "var(--space-sm)", alignItems: "flex-start" }}>
                  <div style={{ backgroundColor: "var(--fg-navy)", color: "#ffffff", padding: "10px", border: "var(--border-thin)" }}>
                    <ArrowRight size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: "1.15rem", marginBottom: "4px", textTransform: "none" }}>Ebbinghaus Memory Decay</h3>
                    <p style={{ fontSize: "0.95rem", color: "var(--fg-navy)" }}>
                      Facts are evaluated on strength, recency, and importance. Regularly accessed notes strengthen; neglected ones decay and are archived.
                    </p>
                  </div>
                </div>
              </div>

            </div>

            <div style={{ position: "relative" }}>
              <div className="ink-image-wrapper" style={{ transform: "rotate(1.5deg)" }}>
                <img 
                  src="https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80" 
                  alt="Brutalist concrete architecture columns and shadows"
                  className="ink-image"
                  style={{ height: "420px", objectFit: "cover" }}
                />
              </div>
              <div 
                className="mono" 
                style={{ 
                  position: "absolute", 
                  top: "-15px", 
                  right: "15px", 
                  backgroundColor: "var(--accent-yellow)", 
                  padding: "4px 12px", 
                  border: "var(--border-thin)",
                  fontWeight: "bold",
                  fontSize: "0.75rem"
                }}
              >
                INGESTION_NODE // COLUMN_LINES
              </div>
            </div>

          </div>

        </div>
      </section>

      {/* Bi-Temporal Time Travel Slider */}
      <section id="timetravel">
        <TimeTravelSlider />
      </section>
    </div>
  );
}
