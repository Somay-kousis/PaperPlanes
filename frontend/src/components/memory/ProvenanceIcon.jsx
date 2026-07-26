import { Quote, Sparkles } from "lucide-react";

export default function ProvenanceIcon({ isUserStated }) {
  const Icon = isUserStated ? Quote : Sparkles;
  const title = isUserStated ? "User stated claim" : "Inferred by the agent graph";
  
  return (
    <span 
      style={{ 
        display: "inline-flex", 
        alignItems: "center", 
        justifyContent: "center",
        width: "20px",
        height: "20px",
        borderRadius: "4px",
        backgroundColor: isUserStated ? "#fef7e0" : "#f0f4ff",
        color: isUserStated ? "#b06000" : "var(--accent-cobalt)"
      }} 
      title={title} 
      aria-label={title}
    >
      <Icon size={11} strokeWidth={2.5} />
    </span>
  );
}
