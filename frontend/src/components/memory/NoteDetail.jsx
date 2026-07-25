import { Brain, AlertTriangle, Loader2 } from "lucide-react";
import StatusBadge from "../StatusBadge.jsx";
import MeterBar from "./MeterBar.jsx";
import ProvenanceIcon from "./ProvenanceIcon.jsx";
import TimelineRow from "./TimelineRow.jsx";
import AuditTrail from "./AuditTrail.jsx";
import EmptyState from "../EmptyState.jsx";
import MemoryGraph from "./MemoryGraph.jsx";

function groupLinksByRelation(links) {
  const groups = new Map();
  for (const link of links ?? []) {
    const key = link.relation_type || "related";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(link);
  }
  return Array.from(groups.entries());
}

/* Shared section heading style for this panel */
function SectionLabel({ children }) {
  return (
    <div
      className="mono-upper text-muted"
      style={{ fontSize: "0.65rem", letterSpacing: "0.1em", borderBottom: "1px solid var(--border-ui)", paddingBottom: "6px", marginBottom: "4px" }}
    >
      {children}
    </div>
  );
}

export default function NoteDetail({ note, loading, onOpenNote }) {
  if (loading) {
    return (
      <div className="mono text-muted" style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "200px", gap: "8px" }}>
        <Loader2 size={15} className="icon-spin" /> Loading note properties…
      </div>
    );
  }

  if (!note) {
    return (
      <EmptyState
        icon={Brain}
        title="Select a note"
        description="Choose a memory from the list to inspect its content, timelines, links, and transactions."
      />
    );
  }

  const linkGroups = groupLinksByRelation(note.links);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>

      {/* 1. Neighborhood Graph Canvas */}
      <MemoryGraph note={note} onOpenNote={onOpenNote} />

      {/* 2. Content */}
      <div className="app-card" style={{ padding: "var(--space-sm)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-xs)" }}>
          <StatusBadge status={note.status} />
          <ProvenanceIcon isUserStated={note.is_user_stated} />
        </div>
        <p className="serif" style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--fg-navy)", lineHeight: 1.55, margin: 0 }}>
          {note.content}
        </p>
      </div>

      {/* 3. Decay & Relevance Metrics */}
      <div className="app-card" style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column", gap: "10px" }}>
        <SectionLabel>Decay &amp; Relevance Metrics</SectionLabel>
        <MeterBar label="Importance" value={note.importance} tone="accent" />
        <MeterBar label="Strength"   value={note.strength}   tone="info" />
        <MeterBar label="Confidence" value={note.confidence} tone="red" />
      </div>

      {/* 4. Bi-Temporal Lifetimes */}
      <div className="app-card" style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column", gap: "10px" }}>
        <SectionLabel>Bi-Temporal Lifetimes</SectionLabel>
        <TimelineRow
          label="Event Time (Valid Range)"
          startLabel="valid"
          startIso={note.valid_at}
          endLabel="invalid"
          endIso={note.invalid_at}
        />
        <TimelineRow
          label="Transaction Time (System Range)"
          startLabel="created"
          startIso={note.created_at}
          endLabel="expired"
          endIso={note.expired_at}
        />
      </div>

      {/* 5. Keywords & Tags */}
      {(note.keywords?.length > 0 || note.tags?.length > 0) && (
        <div className="app-card" style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column", gap: "8px" }}>
          <SectionLabel>Keywords &amp; Tags</SectionLabel>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {note.keywords?.map((keyword) => (
              <span
                key={`kw-${keyword}`}
                className="mono"
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 8px",
                  border: "1px solid var(--accent-yellow)",
                  borderRadius: "100px",
                  backgroundColor: "var(--accent-yellow-light)",
                  color: "#8a6c00",
                }}
              >
                {keyword}
              </span>
            ))}
            {note.tags?.map((tag) => (
              <span
                key={`tag-${tag}`}
                className="mono text-muted"
                style={{
                  fontSize: "0.7rem",
                  padding: "2px 8px",
                  border: "1px solid var(--border-ui)",
                  borderRadius: "100px",
                  backgroundColor: "var(--bg-cream)",
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 6. Derived Chain */}
      {note.derived_from?.length > 0 && (
        <div className="app-card" style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column", gap: "8px" }}>
          <SectionLabel>Derived Chain Dependencies</SectionLabel>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {note.derived_from.map((id) => (
              <button
                type="button"
                key={id}
                className="mono"
                style={{
                  padding: "3px 9px",
                  border: "1px solid var(--border-ui)",
                  borderRadius: "100px",
                  backgroundColor: "var(--accent-cobalt-light)",
                  color: "var(--accent-cobalt)",
                  cursor: "pointer",
                  fontSize: "0.7rem",
                }}
                onClick={() => onOpenNote?.(id)}
              >
                note {String(id).slice(0, 8)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 7. Relation Link Traversals */}
      {linkGroups.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
          {linkGroups.map(([relation, links]) => {
            const isContradiction = relation === "contradicts";
            return (
              <div
                key={relation}
                className={`app-card${isContradiction ? " app-card-red" : ""}`}
                style={{
                  padding: "var(--space-sm)",
                  backgroundColor: isContradiction ? "var(--accent-red-light)" : "var(--bg-card)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                }}
              >
                <div
                  className="mono-upper"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "5px",
                    fontSize: "0.65rem",
                    letterSpacing: "0.1em",
                    color: isContradiction ? "var(--accent-red)" : "var(--fg-muted)",
                  }}
                >
                  {isContradiction && <AlertTriangle size={11} />}
                  {relation} ({links.length})
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {links.map((link) => (
                    <button
                      type="button"
                      key={link.id}
                      style={{
                        padding: "var(--space-xs)",
                        border: "1px solid var(--border-ui)",
                        borderRadius: "5px",
                        backgroundColor: "var(--bg-card)",
                        textAlign: "left",
                        cursor: "pointer",
                        display: "flex",
                        flexDirection: "column",
                        gap: "4px",
                        width: "100%",
                        transition: "box-shadow 0.15s ease",
                      }}
                      onClick={() => onOpenNote?.(link.other?.id)}
                    >
                      <div
                        className="mono-upper text-muted"
                        style={{ fontSize: "0.62rem", color: isContradiction ? "var(--accent-red)" : undefined }}
                      >
                        {relation} · {link.direction}
                      </div>
                      <div className="serif" style={{ fontSize: "0.93rem", color: "var(--fg-navy)", lineHeight: 1.4 }}>
                        "{link.other?.content}"
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "2px", width: "100%" }}>
                        <span className="mono text-muted" style={{ fontSize: "0.7rem" }}>
                          Confidence: {Math.round((link.other?.confidence ?? 0.8) * 100)}%
                        </span>
                        <StatusBadge status={link.other?.status} />
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 8. Audit Trail */}
      <div className="app-card" style={{ padding: "var(--space-sm)", display: "flex", flexDirection: "column" }}>
        <SectionLabel>Audit Trail Log ({note.audit?.length ?? 0})</SectionLabel>
        <AuditTrail entries={note.audit} onOpenNote={onOpenNote} />
      </div>

    </div>
  );
}
