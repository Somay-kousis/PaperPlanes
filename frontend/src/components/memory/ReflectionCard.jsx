import { Sparkles } from "lucide-react";
import MeterBar from "./MeterBar.jsx";
import { formatRelativeTime } from "../../lib/format.js";

const TRIGGER_LABELS = {
  manual: "Manual",
  scheduled: "Scheduled",
  importance_threshold: "Importance threshold",
};

/** A single distilled reflection, with the memories it cites as clickable chips. */
export default function ReflectionCard({ reflection, unavailableCiteIds, onOpenCite }) {
  const cites = reflection.cites ?? [];

  return (
    <div className="card reflection-card">
      <div className="reflection-card-header">
        <span className="pill pill-info">
          <Sparkles size={11} /> {TRIGGER_LABELS[reflection.trigger_reason] ?? reflection.trigger_reason}
        </span>
        <span className="text-muted">{formatRelativeTime(reflection.created_at)}</span>
      </div>

      <p className="reflection-card-content">{reflection.content}</p>

      <MeterBar label="Importance" value={reflection.importance} tone="accent" />

      {cites.length > 0 && (
        <div className="reflection-card-cites">
          <span className="text-muted">
            Cites {cites.length} {cites.length === 1 ? "memory" : "memories"}
          </span>
          <div className="derived-chain">
            {cites.map((id) => {
              const unavailable = unavailableCiteIds?.has(id);
              return (
                <button
                  key={id}
                  type="button"
                  className={"derived-chain-item" + (unavailable ? " derived-chain-item-unavailable" : "")}
                  onClick={() => onOpenCite?.(id)}
                  disabled={unavailable}
                  title={unavailable ? "Note is archived or no longer available" : undefined}
                >
                  {String(id).slice(0, 8)}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
