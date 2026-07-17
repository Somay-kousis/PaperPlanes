import { Loader2, CheckCircle2, XCircle, Clock, Archive } from "lucide-react";

const IN_PROGRESS_STATUSES = new Set(["pending", "parsing", "embedding", "extracting"]);

const STATUS_CONFIG = {
  pending: { label: "Pending", pillClass: "pill-neutral", Icon: Clock },
  parsing: { label: "Parsing", pillClass: "pill-info", Icon: Loader2 },
  embedding: { label: "Embedding", pillClass: "pill-info", Icon: Loader2 },
  extracting: { label: "Extracting", pillClass: "pill-info", Icon: Loader2 },
  ready: { label: "Ready", pillClass: "pill-success", Icon: CheckCircle2 },
  failed: { label: "Failed", pillClass: "pill-danger", Icon: XCircle },
  // Memory note lifecycle statuses (bi-temporal memory model).
  active: { label: "Active", pillClass: "pill-success", Icon: CheckCircle2 },
  archived: { label: "Archived", pillClass: "pill-neutral", Icon: Archive },
  invalidated: { label: "Invalidated", pillClass: "pill-danger", Icon: XCircle },
};

/** True once a paper has left the parsing/embedding pipeline (ready or failed). */
export function isTerminalStatus(status) {
  return !IN_PROGRESS_STATUSES.has(status);
}

export default function StatusBadge({ status, failReason }) {
  const config = STATUS_CONFIG[status] ?? {
    label: status || "Unknown",
    pillClass: "pill-neutral",
    Icon: Clock,
  };
  const { label, pillClass, Icon } = config;
  const pulsing = IN_PROGRESS_STATUSES.has(status);

  return (
    <span
      className={"pill " + pillClass + (pulsing ? " pill-pulse" : "")}
      title={status === "failed" && failReason ? failReason : undefined}
    >
      <Icon size={11} className={pulsing ? "icon-spin" : undefined} aria-hidden="true" />
      {label}
    </span>
  );
}
