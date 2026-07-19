import { useCallback, useEffect, useState } from "react";
import { GitCompareArrows, Loader2 } from "lucide-react";

import { getContradictions, resolveContradiction } from "../lib/api.js";
import EmptyState from "../components/EmptyState.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import ContradictionCard from "../components/ContradictionCard.jsx";

const FILTERS = [
  { key: "unresolved", label: "Unresolved", params: { resolved: false } },
  { key: "resolved",   label: "Resolved",   params: { resolved: true } },
  { key: "all",        label: "All",         params: {} },
];
const POLL_INTERVAL_MS = 5000;

export default function ContradictionsPage() {
  const [filter, setFilter] = useState("unresolved");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchItems = useCallback(
    async ({ silent = false, options = {} } = {}) => {
      if (!silent) setLoading(true);
      try {
        const params = FILTERS.find((f) => f.key === filter)?.params ?? {};
        const data = await getContradictions({ ...params, limit: 50 }, options);
        setItems(data);
        setError(null);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err);
        }
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [filter],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchItems({ options: { signal: controller.signal } });
    return () => { controller.abort(); };
  }, [fetchItems]);

  useEffect(() => {
    const controller = new AbortController();
    let inFlight = false;

    async function tick() {
      if (document.visibilityState !== "visible" || inFlight || controller.signal.aborted) return;
      inFlight = true;
      try {
        await fetchItems({ silent: true, options: { signal: controller.signal } });
      } finally {
        inFlight = false;
      }
    }
    const id = setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
      controller.abort();
    };
  }, [fetchItems]);

  async function handleResolve(id, resolutionNote) {
    const result = await resolveContradiction(id, resolutionNote);
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
    <div className="inner-page">
      <div className="brutalist-container">

        {/* ── Page Header ──────────────────────────────────────────────── */}
        <header className="page-header">
          <div className="page-header-left">
            <div className="page-counter">
              <span className="page-counter-num">04 / Clashes</span>
            </div>
            <h2 className="inner-h2">Contradictions Matrix</h2>
            <p className="page-subtitle">
              Reconcile conflicting claims extracted from different research publications.
            </p>
          </div>
          <div className="page-header-actions">
            <div className="filter-pill-group">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  className={`filter-pill${filter === f.key ? " active" : ""}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        </header>

        {error && (
          <ErrorBanner
            title="Database Connection Error"
            message={error.message}
            onDismiss={() => setError(null)}
          />
        )}

        {/* ── Contradiction Card List ──────────────────────────────────── */}
        <div style={{ maxWidth: "860px" }}>
          {loading ? (
            <p className="text-muted" style={{ display: "flex", gap: "7px", alignItems: "center" }}>
              <Loader2 size={13} className="icon-spin" /> Querying claim logs…
            </p>
          ) : items.length === 0 ? (
            <EmptyState
              icon={GitCompareArrows}
              title="No claim discrepancies"
              description="Ingest research manuscripts that assert contradictory theories to trigger live system warnings."
            />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-md)" }}>
              {items.map((item) => (
                <ContradictionCard key={item.id} contradiction={item} onResolve={handleResolve} />
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
