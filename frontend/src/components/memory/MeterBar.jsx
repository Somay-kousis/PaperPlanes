import { clamp01 } from "../../lib/format.js";

/** Thin horizontal meter used for importance/strength/confidence scores (0-1). */
export default function MeterBar({ label, value, tone = "accent" }) {
  const pct = Math.round(clamp01(value) * 100);
  return (
    <div className="meter" title={`${label}: ${pct}%`}>
      <span className="meter-label">{label}</span>
      <span className="meter-track">
        <span className={`meter-fill meter-fill-${tone}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="meter-value">{pct}%</span>
    </div>
  );
}
