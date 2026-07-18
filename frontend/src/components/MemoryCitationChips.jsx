import { Brain } from "lucide-react";

/**
 * Chips for memory-backed citations (`reply.memory_citations`), distinct from
 * paper citations: brain icon, info accent, tooltip shows the snippet + score.
 */
export default function MemoryCitationChips({ citations }) {
  if (!citations || citations.length === 0) return null;

  return (
    <div className="citation-row" aria-label="Memory sources">
      {citations.map((citation, index) => {
        const score = typeof citation.score === "number" ? citation.score.toFixed(2) : null;
        const title = [citation.snippet, score != null ? `score ${score}` : null]
          .filter(Boolean)
          .join(" · ");
        return (
          <span
            key={citation.note_id ?? index}
            className="citation-chip citation-chip-memory"
            title={title || undefined}
            tabIndex={0}
          >
            <Brain size={11} />
            {citation.snippet ? citation.snippet.slice(0, 60) : `Memory ${index + 1}`}
          </span>
        );
      })}
    </div>
  );
}
