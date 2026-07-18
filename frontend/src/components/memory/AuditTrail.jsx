import { History } from "lucide-react";
import AuditRow from "./AuditRow.jsx";
import EmptyState from "../EmptyState.jsx";

export default function AuditTrail({ entries, showTarget = false, onOpenNote }) {
  if (!entries || entries.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No history yet"
        description="Changes to this note — additions, updates, invalidations — will show up here."
      />
    );
  }

  return (
    <div className="audit-trail">
      {entries.map((entry) => (
        <AuditRow key={entry.id} entry={entry} showTarget={showTarget} onOpenNote={onOpenNote} />
      ))}
    </div>
  );
}
