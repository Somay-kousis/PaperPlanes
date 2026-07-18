import { useCallback, useEffect, useState } from "react";
import { GitCompareArrows } from "lucide-react";

import { getContradictions, resolveContradiction } from "../lib/api.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import ContradictionCard from "../components/ContradictionCard.jsx";

const FILTERS = [
  { key: "unresolved", label: "Unresolved", params: { resolved: false } },
  { key: "resolved", label: "Resolved", params: { resolved: true } },
  { key: "all", label: "All", params: {} },
];
const POLL_INTERVAL_MS = 5000;

export default function ContradictionsPage() {
  const [filter, setFilter] = useState("unresolved");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchItems = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setLoading(true);
      try {
        const params = FILTERS.find((f) => f.key === filter)?.params ?? {};
        const data = await getContradictions({ ...params, limit: 50 });
        setItems(data);
        setError(null);
      } catch (err) {
        setError(err);
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [filter],
  );

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Poll for newly-detected contradictions every 5s, but only while the tab
  // is actually visible — keeps a live demo feeling without hammering the
  // backend when the page is backgrounded.
  useEffect(() => {
    function tick() {
      if (document.visibilityState === "visible") fetchItems({ silent: true });
    }
    const intervalId = setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [fetchItems]);

  async function handleResolve(id, resolutionNote) {
    const result = await resolveContradiction(id, resolutionNote);
    // Optimistically flip the card to resolved right away, then reconcile
    // with the server (this also drops it from the "unresolved" view).
    setItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, resolved: true, resolution_note: result?.resolution_note ?? resolutionNote ?? null }
          : item,
      ),
    );
    fetchItems({ silent: true });
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Contradictions</h1>
          <p className="page-subtitle">
            Where PaperPlanes noticed two sources — or two memories — disagree.
          </p>
        </div>
        <div className="pill-toggle-group" role="group" aria-label="Contradiction filter">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={"pill-toggle" + (filter === f.key ? " active" : "")}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <ErrorBanner
          title="Could not reach the backend"
          message={error.message}
          onDismiss={() => setError(null)}
        />
      )}

      {loading ? (
        <p className="text-muted pane-loading">Loading contradictions…</p>
      ) : items.length === 0 ? (
        <EmptyState
          icon={GitCompareArrows}
          title="No contradictions found yet"
          description="Ingest two papers that make competing claims and PaperPlanes will flag them here."
        />
      ) : (
        <div className="card-list">
          {items.map((item) => (
            <ContradictionCard key={item.id} contradiction={item} onResolve={handleResolve} />
          ))}
        </div>
      )}
    </div>
  );
}
