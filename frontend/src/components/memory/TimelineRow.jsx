import { formatDateTime } from "../../lib/format.js";

/**
 * One labeled timeline (event time or system time), rendered as a small bar
 * with a start dot, a line, and an end dot — dashed/pulsing when open-ended.
 */
export default function TimelineRow({ label, startLabel, startIso, endLabel, endIso }) {
  const ongoing = !endIso;
  return (
    <div className="timeline-row">
      <div className="timeline-row-label">{label}</div>
      <div className="timeline-track">
        <span className="timeline-dot timeline-dot-start" />
        <span className={"timeline-line" + (ongoing ? " timeline-line-ongoing" : "")} />
        <span className={"timeline-dot timeline-dot-end" + (ongoing ? " timeline-dot-ongoing" : "")} />
      </div>
      <div className="timeline-labels text-muted">
        <span>
          {startLabel}: {formatDateTime(startIso) || "—"}
        </span>
        <span>{ongoing ? `${endLabel}: ongoing` : `${endLabel}: ${formatDateTime(endIso)}`}</span>
      </div>
    </div>
  );
}
