import { useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { formatRelativeTime } from "../lib/format.js";

const PRESETS = [
  { label: "Outdated",      note: "Resolved: Outdated claim." },
  { label: "Complementary", note: "Resolved: Both claims complement each other." },
  { label: "Superseded",    note: "Resolved: Claim B supersedes Claim A." },
];

export default function ContradictionCard({ contradiction, onResolve }) {
  const [resolving, setResolving]   = useState(false);
  const [note, setNote]             = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await onResolve(contradiction.id, note.trim() || undefined);
      setResolving(false);
      setNote("");
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className={`app-card${contradiction.resolved ? "" : " app-card-orange"}`}
      style={{
        padding: "var(--space-sm)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-sm)",
        boxShadow: contradiction.resolved ? "var(--shadow-card)" : "0 2px 6px rgba(232,105,26,0.12)",
      }}
    >
      {/* Competing Claims */}
      <div className="b-grid-2" style={{ gap: "var(--space-md)" }}>

        {/* Claim A */}
        <div style={{ borderLeft: "3px solid var(--accent-red)", paddingLeft: "var(--space-xs)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <div className="mono-upper" style={{ fontSize: "0.65rem", color: "var(--accent-red)", letterSpacing: "0.1em" }}>
            Claim A
          </div>
          <p className="serif" style={{ fontSize: "1rem", fontWeight: 600, color: "var(--fg-navy)", margin: "3px 0", lineHeight: 1.4 }}>
            "{contradiction.claim_a?.statement}"
          </p>
          <span className="mono text-muted" style={{ fontSize: "0.72rem" }} title={contradiction.claim_a?.paper_title}>
            Source: {contradiction.claim_a?.paper_title || "Unknown manuscript"}
          </span>
        </div>

        {/* Claim B */}
        <div style={{ borderLeft: "3px solid var(--accent-cobalt)", paddingLeft: "var(--space-xs)", display: "flex", flexDirection: "column", gap: "4px" }}>
          <div className="mono-upper" style={{ fontSize: "0.65rem", color: "var(--accent-cobalt)", letterSpacing: "0.1em" }}>
            Claim B
          </div>
          <p className="serif" style={{ fontSize: "1rem", fontWeight: 600, color: "var(--fg-navy)", margin: "3px 0", lineHeight: 1.4 }}>
            "{contradiction.claim_b?.statement}"
          </p>
          <span className="mono text-muted" style={{ fontSize: "0.72rem" }} title={contradiction.claim_b?.paper_title}>
            Source: {contradiction.claim_b?.paper_title || "Unknown manuscript"}
          </span>
        </div>

      </div>

      {/* Rationale alert */}
      {contradiction.rationale && (
        <div
          style={{
            display: "flex",
            gap: "8px",
            alignItems: "flex-start",
            backgroundColor: "var(--accent-yellow-light)",
            border: "1px solid var(--accent-yellow)",
            borderRadius: "5px",
            padding: "10px 12px",
            fontSize: "0.88rem",
            color: "var(--fg-navy)",
            lineHeight: 1.5,
          }}
        >
          <AlertTriangle size={14} style={{ color: "#8a6c00", flexShrink: 0, marginTop: "2px" }} />
          <p style={{ margin: 0 }}>{contradiction.rationale}</p>
        </div>
      )}

      {/* Footer — timestamps + resolution actions */}
      <div
        style={{
          borderTop: "1px solid var(--border-ui)",
          paddingTop: "var(--space-xs)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "var(--space-sm)",
        }}
      >
        <span className="mono text-muted" style={{ fontSize: "0.72rem" }}>
          Detected {formatRelativeTime(contradiction.detected_at)}
        </span>

        {contradiction.resolved ? (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="status-pill status-pill-cobalt">
              <CheckCircle2 size={11} /> Resolved
            </span>
            {contradiction.resolution_note && (
              <span className="serif text-muted" style={{ fontSize: "0.82rem", fontStyle: "italic" }}>
                ({contradiction.resolution_note})
              </span>
            )}
          </div>
        ) : resolving ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%" }}>
            {/* Preset shortcuts */}
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
              {PRESETS.map(({ label, note: presetNote }) => (
                <button
                  key={label}
                  type="button"
                  className="filter-pill"
                  style={{ fontFamily: "var(--font-sans)", textTransform: "none", letterSpacing: "normal", fontSize: "0.8rem" }}
                  onClick={() => setNote(presetNote)}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Custom note + submit */}
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input
                type="text"
                placeholder="Resolution note (optional)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                disabled={submitting}
                className="app-input"
                autoFocus
              />
              <button
                type="button"
                className="brutalist-btn brutalist-btn-primary brutalist-btn-sm"
                onClick={handleSubmit}
                disabled={submitting}
                style={{ flexShrink: 0 }}
              >
                {submitting ? "Resolving…" : "Confirm"}
              </button>
              <button
                type="button"
                className="brutalist-btn brutalist-btn-sm"
                onClick={() => { setResolving(false); setError(null); }}
                disabled={submitting}
                style={{ flexShrink: 0 }}
              >
                Cancel
              </button>
            </div>
            {error && (
              <span className="mono" style={{ color: "var(--accent-red)", fontSize: "0.78rem" }}>
                {error.message}
              </span>
            )}
          </div>
        ) : (
          <button
            type="button"
            className="brutalist-btn brutalist-btn-sm"
            onClick={() => setResolving(true)}
          >
            Resolve Claim
          </button>
        )}
      </div>
    </div>
  );
}
