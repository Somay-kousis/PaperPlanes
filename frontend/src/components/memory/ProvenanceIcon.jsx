import { Quote, Sparkle } from "lucide-react";

/** User-stated notes get a quote mark, agent-inferred notes get a sparkle. */
export default function ProvenanceIcon({ isUserStated }) {
  const Icon = isUserStated ? Quote : Sparkle;
  const title = isUserStated ? "User-stated" : "Inferred by the agent";
  return (
    <span className="provenance-icon" title={title} aria-label={title}>
      <Icon size={12} strokeWidth={2} />
    </span>
  );
}
