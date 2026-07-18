function stringifyValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/**
 * Field-level diff between two flat snapshots (audit `details.before` /
 * `details.after`). Only changed fields are rendered; `content` gets its own
 * stacked before/after block since it's usually multi-line prose.
 */
export default function MemoryDiffViewer({ before, after }) {
  if (!before || !after) return null;

  const keys = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).filter(
    (key) => stringifyValue(before[key]) !== stringifyValue(after[key]),
  );

  if (keys.length === 0) return null;

  return (
    <div className="diff-list">
      {keys.map((key) => {
        const oldValue = stringifyValue(before[key]);
        const newValue = stringifyValue(after[key]);
        if (key === "content") {
          return (
            <div className="diff-content-blocks" key={key}>
              <div className="diff-field-name">content</div>
              <div className="diff-block diff-block-old">{oldValue}</div>
              <div className="diff-block diff-block-new">{newValue}</div>
            </div>
          );
        }
        return (
          <div className="diff-field-row" key={key}>
            <span className="diff-field-name">{key}</span>
            <span className="diff-old">{oldValue}</span>
            <span className="diff-arrow">→</span>
            <span className="diff-new">{newValue}</span>
          </div>
        );
      })}
    </div>
  );
}
