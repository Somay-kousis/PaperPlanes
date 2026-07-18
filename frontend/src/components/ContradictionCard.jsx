import { useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { formatRelativeTime } from "../lib/format.js";
import use3dTilt from "../lib/use3dTilt.js";

export default function ContradictionCard({ contradiction, onResolve }) {
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const cardTilt = use3dTilt(6, 1.02);

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
    <div className={`card contradiction-card ${!contradiction.resolved ? "contradiction-card-unresolved" : ""}`} style={{ transition: "all var(--transition-base)" }}>
      <div className="contradiction-claims-split">
        <div
          className="contradiction-claim-pane source-a"
          onMouseMove={cardTilt.onMouseMove}
          onMouseLeave={cardTilt.onMouseLeave}
          onMouseEnter={cardTilt.onMouseEnter}
        >
          <div className="contradiction-claim-label text-muted" style={{ fontWeight: 600, fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--danger)" }}>
            Claim A
          </div>
          <p className="contradiction-claim-statement" style={{ margin: "var(--space-2) 0", fontSize: "13.5px", fontWeight: "500", color: "var(--text-primary)" }}>
            {contradiction.claim_a?.statement}
          </p>
          <div className="contradiction-claim-meta">
            <span className="pill pill-neutral contradiction-claim-paper" title={contradiction.claim_a?.paper_title} style={{ maxWidth: "100%" }}>
              {contradiction.claim_a?.paper_title || "Unknown paper"}
            </span>
          </div>
        </div>
        <div
          className="contradiction-claim-pane source-b"
          onMouseMove={cardTilt.onMouseMove}
          onMouseLeave={cardTilt.onMouseLeave}
          onMouseEnter={cardTilt.onMouseEnter}
        >
          <div className="contradiction-claim-label text-muted" style={{ fontWeight: 600, fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--info)" }}>
            Claim B
          </div>
          <p className="contradiction-claim-statement" style={{ margin: "var(--space-2) 0", fontSize: "13.5px", fontWeight: "500", color: "var(--text-primary)" }}>
            {contradiction.claim_b?.statement}
          </p>
          <div className="contradiction-claim-meta">
            <span className="pill pill-neutral contradiction-claim-paper" title={contradiction.claim_b?.paper_title} style={{ maxWidth: "100%" }}>
              {contradiction.claim_b?.paper_title || "Unknown paper"}
            </span>
          </div>
        </div>
      </div>

      <div className="contradiction-rationale">
        <AlertTriangle size={14} strokeWidth={2} style={{ flexShrink: 0, marginTop: 1 }} />
        <p>{contradiction.rationale}</p>
      </div>

      <div className="contradiction-footer" style={{ minHeight: "44px" }}>
        <span className="text-muted">{formatRelativeTime(contradiction.detected_at)}</span>

        {contradiction.resolved ? (
          <span className="flex-row">
            <span className="pill pill-neutral">
              <CheckCircle2 size={11} className="text-success" /> Resolved
            </span>
            {contradiction.resolution_note && (
              <span className="text-muted" style={{ fontStyle: "italic" }}>{contradiction.resolution_note}</span>
            )}
          </span>
        ) : resolving ? (
          <div className="contradiction-resolve-form" style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "var(--space-2)", width: "100%", marginTop: "var(--space-2)" }}>
            <div className="resolution-shortcuts">
              <button type="button" className="resolution-btn-tag" onClick={() => setNote("Resolved: Outdated claim.")}>
                Outdated
              </button>
              <button type="button" className="resolution-btn-tag" onClick={() => setNote("Resolved: Both claims complement each other.")}>
                Complementary
              </button>
              <button type="button" className="resolution-btn-tag" onClick={() => setNote("Resolved: Claim B supersedes Claim A.")}>
                Superseded
              </button>
            </div>
            <div style={{ display: "flex", width: "100%", gap: "var(--space-2)", alignItems: "center", flexWrap: "wrap" }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder="Resolution note (optional)"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                disabled={submitting}
                autoFocus
              />
              <button type="button" className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
                {submitting ? "Resolving…" : "Confirm"}
              </button>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setResolving(false);
                  setError(null);
                }}
                disabled={submitting}
              >
                Cancel
              </button>
            </div>
            {error && <span className="contradiction-resolve-error">{error.message}</span>}
          </div>
        ) : (
          <button type="button" className="btn btn-primary" style={{ background: "var(--bg-surface-raised)", border: "1px solid var(--border-default)", color: "var(--text-primary)" }} onClick={() => setResolving(true)}>
            Resolve
          </button>
        )}
      </div>
    </div>
  );
}
