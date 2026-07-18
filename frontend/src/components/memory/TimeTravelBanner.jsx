import { History, X } from "lucide-react";
import { formatDateTime } from "../../lib/format.js";

/** Prominent banner shown whenever the "as of" time-travel filter is active. */
export default function TimeTravelBanner({ asOf, onClear }) {
  if (!asOf) return null;
  return (
    <div className="time-travel-banner" role="status">
      <History size={15} strokeWidth={2} />
      <span>
        Time-travel view: <strong>{formatDateTime(asOf)}</strong> — showing what PaperPlanes
        believed at this moment.
      </span>
      <button
        type="button"
        className="time-travel-clear"
        onClick={onClear}
        aria-label="Return to now"
        title="Return to now"
      >
        <X size={15} />
      </button>
    </div>
  );
}
