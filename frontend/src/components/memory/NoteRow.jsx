import { Eye } from "lucide-react";
import StatusBadge from "../StatusBadge.jsx";
import MeterBar from "./MeterBar.jsx";
import ProvenanceIcon from "./ProvenanceIcon.jsx";
import { formatRelativeTime } from "../../lib/format.js";

export default function NoteRow({ note, selected, onClick }) {
  return (
    <button
      type="button"
      className={"note-row" + (selected ? " selected" : "")}
      onClick={onClick}
    >
      <div className="note-row-header">
        <p className="note-row-content">{note.content}</p>
        <StatusBadge status={note.status} />
      </div>

      {note.tags && note.tags.length > 0 && (
        <div className="note-row-tags">
          {note.tags.map((tag) => (
            <span className="tag-chip" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="note-row-meters">
        <MeterBar label="Importance" value={note.importance} tone="accent" />
        <MeterBar label="Strength" value={note.strength} tone="info" />
      </div>

      <div className="note-row-footer text-muted">
        <span className="flex-row">
          <ProvenanceIcon isUserStated={note.is_user_stated} />
          <span className="flex-row">
            <Eye size={12} /> {note.access_count ?? 0}
          </span>
        </span>
        <span>{formatRelativeTime(note.created_at)}</span>
      </div>
    </button>
  );
}
