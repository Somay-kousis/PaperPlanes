/**
 * Numbered citation chips rendered under an assistant message, e.g.
 * "[1] Attention Is All You Need · p.12". The snippet shows on hover/focus
 * via the native title tooltip.
 */
export default function CitationChips({ citations }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="citation-row" aria-label="Sources">
      {citations.map((citation, index) => {
        const label = citation.paper_title || "Untitled paper";
        const page = citation.page_number != null ? ` · p.${citation.page_number}` : "";
        return (
          <span
            key={citation.chunk_id ?? `${citation.paper_id ?? "paper"}-${index}`}
            className="citation-chip"
            title={citation.snippet || undefined}
            tabIndex={0}
          >
            <span className="citation-chip-index">[{index + 1}]</span>
            {label}
            {page}
          </span>
        );
      })}
    </div>
  );
}
