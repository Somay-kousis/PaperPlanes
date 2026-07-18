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

export default function NoteDetail({ note, loading, onOpenNote }) {
  if (loading) {
    return (
      <div className="side-panel-loading text-muted">
        <Loader2 size={16} className="icon-spin" /> Loading note…
      </div>
    );
  }

  if (!note) {
    return (
      <EmptyState
        icon={Brain}
        title="Select a note"
        description="Choose a memory from the list to inspect its full content, timelines, links, and audit history."
      />
    );
  }

  const linkGroups = groupLinksByRelation(note.links);

  return (
    <div className="note-detail">
      <MemoryGraph note={note} onOpenNote={onOpenNote} />

      <div className="note-detail-section">
        <div className="note-detail-top">
          <StatusBadge status={note.status} />
          <ProvenanceIcon isUserStated={note.is_user_stated} />
        </div>
        <p className="note-detail-content">{note.content}</p>
      </div>

      <div className="note-detail-section">
        <div className="note-detail-label">Scores</div>
        <MeterBar label="Importance" value={note.importance} tone="accent" />
        <MeterBar label="Strength" value={note.strength} tone="info" />
        <MeterBar label="Confidence" value={note.confidence} tone="success" />
      </div>

      <div className="note-detail-section">
        <div className="note-detail-label">Timelines</div>
        <TimelineRow
          label="Event time"
          startLabel="valid"
          startIso={note.valid_at}
          endLabel="invalid"
          endIso={note.invalid_at}
        />
        <TimelineRow
          label="System time"
          startLabel="created"
          startIso={note.created_at}
          endLabel="expired"
          endIso={note.expired_at}
        />
      </div>

      {(note.keywords?.length > 0 || note.tags?.length > 0) && (
        <div className="note-detail-section">
          <div className="note-detail-label">Keywords &amp; tags</div>
          <div className="note-row-tags">
            {note.keywords?.map((keyword) => (
              <span className="tag-chip tag-chip-keyword" key={`kw-${keyword}`}>
                {keyword}
              </span>
            ))}
            {note.tags?.map((tag) => (
              <span className="tag-chip" key={`tag-${tag}`}>
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}

      {note.derived_from?.length > 0 && (
        <div className="note-detail-section">
          <div className="note-detail-label">Derived from</div>
          <div className="derived-chain">
            {note.derived_from.map((id) => (
              <button
                type="button"
                key={id}
                className="derived-chain-item"
                onClick={() => onOpenNote?.(id)}
              >
                {String(id).slice(0, 8)}
              </button>
            ))}
          </div>
        </div>
      )}

      {linkGroups.length > 0 && (
        <div className="note-detail-section">
          <div className="note-detail-label">Links</div>
          {linkGroups.map(([relation, links]) => (
            <div className="link-group" key={relation} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
              <div className={"link-group-title" + (relation === "contradicts" ? " link-group-title-danger" : "")} style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                {relation === "contradicts" && <AlertTriangle size={12} />}
                <span style={{ textTransform: "capitalize", fontWeight: "600" }}>{relation}</span> ({links.length})
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-2)" }}>
                {links.map((link) => (
                  <button
                    type="button"
                    key={link.id}
                    className="traverse-link-card"
                    onClick={() => onOpenNote?.(link.other?.id)}
                  >
                    <div className={`traverse-link-relation ${relation === "contradicts" ? "relation-contradicts" : ""}`}>
                      {relation} &middot; {link.direction}
                    </div>
                    <div className="traverse-link-content">
                      {link.other?.content}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "auto" }}>
                      <span className="text-muted" style={{ fontSize: "10px" }}>Confidence: {Math.round((link.other?.confidence ?? 0.8) * 100)}%</span>
                      <StatusBadge status={link.other?.status} />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="note-detail-section">
        <div className="note-detail-label">Audit trail</div>
        <AuditTrail entries={note.audit} />
      </div>
    </div>
  );
}
