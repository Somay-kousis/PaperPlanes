import { Brain } from "lucide-react";

export default function MemoryCitationChips({ citations }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div 
      style={{ 
        display: "flex", 
        flexWrap: "wrap", 
        gap: "6px", 
        marginTop: "6px" 
      }} 
      aria-label="Memory sources"
    >
      {citations.map((citation, index) => {
        const score = typeof citation.score === "number" ? citation.score.toFixed(2) : null;
        const title = [citation.snippet, score != null ? `score ${score}` : null]
          .filter(Boolean)
          .join(" · ");
        return (
          <span
            key={citation.note_id ?? index}
            title={title || undefined}
            tabIndex={0}
            className="mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              fontSize: "0.7rem",
              padding: "3px 8px",
              border: "1px solid var(--border-ui)",
              borderRadius: "100px",
              backgroundColor: "var(--accent-cobalt-light)",
              color: "var(--accent-cobalt)",
              cursor: "help"
            }}
          >
            <Brain size={12} style={{ flexShrink: 0 }} />
            {citation.snippet ? citation.snippet.slice(0, 60) : `Memory ${index + 1}`}
          </span>
        );
      })}
    </div>
  );
}
