import { Loader2, CheckCircle2, XCircle, Clock, Archive } from "lucide-react";

const IN_PROGRESS_STATUSES = new Set(["pending", "parsing", "embedding", "extracting"]);

const STATUS_CONFIG = {
  pending: { label: "Pending", badgeClass: "badge-cream", Icon: Clock },
  parsing: { label: "Parsing", badgeClass: "badge-yellow", Icon: Loader2 },
  embedding: { label: "Embedding", badgeClass: "badge-yellow", Icon: Loader2 },
  extracting: { label: "Extracting", badgeClass: "badge-yellow", Icon: Loader2 },
  ready: { label: "Ready", badgeClass: "badge-cobalt", Icon: CheckCircle2 },
  failed: { label: "Failed", badgeClass: "badge-red", Icon: XCircle },
  active: { label: "Active", badgeClass: "badge-cobalt", Icon: CheckCircle2 },
  archived: { label: "Archived", badgeClass: "badge-cream", Icon: Archive },
  invalidated: { label: "Invalidated", badgeClass: "badge-red", Icon: XCircle },
};

export function isTerminalStatus(status) {
  return !IN_PROGRESS_STATUSES.has(status);
}

export default function StatusBadge({ status, failReason }) {
  const config = STATUS_CONFIG[status] ?? {
    label: status || "Unknown",
    badgeClass: "badge-cream",
    Icon: Clock,
  };
  const { label, badgeClass, Icon } = config;
  const pulsing = IN_PROGRESS_STATUSES.has(status);

  return (
    <span
      className={`badge ${badgeClass}`}
      title={status === "failed" && failReason ? failReason : undefined}
      style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
    >
      <Icon size={12} className={pulsing ? "icon-spin" : undefined} aria-hidden="true" />
      {label}
    </span>
  );
}
