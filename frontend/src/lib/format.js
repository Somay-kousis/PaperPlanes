// ---------------------------------------------------------------------------
// Small formatting helpers shared by the memory inspector + chat UI.
// ---------------------------------------------------------------------------

const RELATIVE_UNITS = [
  { limit: 60, divisor: 1, unit: "s" },
  { limit: 3600, divisor: 60, unit: "m" },
  { limit: 86400, divisor: 3600, unit: "h" },
  { limit: 2592000, divisor: 86400, unit: "d" },
  { limit: 31536000, divisor: 2592000, unit: "mo" },
];

/** "3m ago" / "2h ago" / "just now"; falls back to a locale date for old timestamps. */
export function formatRelativeTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const diffSeconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (diffSeconds < 5) return "just now";
  if (diffSeconds < 0) return formatDateTime(iso);

  for (const { limit, divisor, unit } of RELATIVE_UNITS) {
    if (diffSeconds < limit) {
      return `${Math.max(1, Math.floor(diffSeconds / divisor))}${unit} ago`;
    }
  }
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function formatDateTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Convert a `datetime-local` input value into an ISO string (UTC-normalized by the Date constructor). */
export function localInputToIso(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString();
}

export function clamp01(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return 0;
  return Math.min(1, Math.max(0, n));
}
