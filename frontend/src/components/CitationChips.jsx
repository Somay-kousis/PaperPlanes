export default function CitationChips({ citations }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div 
      style={{ 
        display: "flex", 
        flexWrap: "wrap", 
        gap: "6px", 
        marginTop: "8px" 
      }} 
      aria-label="Sources"
    >
      {citations.map((citation, index) => {
        const label = citation.paper_title || "Untitled paper";
        const page = citation.page_number != null ? ` · p.${citation.page_number}` : "";
        return (
          <span
            key={citation.chunk_id ?? `${citation.paper_id ?? "paper"}-${index}`}
            title={citation.snippet || undefined}
            tabIndex={0}
            className="mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              fontSize: "0.7rem",
              padding: "3px 8px",
              border: "1px solid var(--border-ui)",
              borderRadius: "100px",
              backgroundColor: "var(--bg-cream)",
              color: "var(--fg-navy)",
              cursor: "help"
            }}
          >
            <span style={{ fontWeight: "bold", marginRight: "4px", color: "var(--accent-cobalt)" }}>[{index + 1}]</span>
            {label}
            {page}
          </span>
        );
      })}
    </div>
  );
}
