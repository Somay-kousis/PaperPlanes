export default function EmptyState({ icon: Icon, title, description }) {
  return (
    <div
      style={{
        padding: "var(--space-lg) var(--space-md)",
        textAlign: "center",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "var(--space-xs)",
      }}
    >
      {Icon && (
        <span
          style={{
            display: "inline-flex",
            padding: "14px",
            borderRadius: "50%",
            backgroundColor: "var(--accent-cobalt-light)",
            color: "var(--accent-cobalt)",
            marginBottom: "var(--space-xs)",
          }}
        >
          <Icon size={26} />
        </span>
      )}
      <h3 className="inner-h3">{title}</h3>
      <p className="text-muted" style={{ maxWidth: "400px", lineHeight: 1.55 }}>{description}</p>
    </div>
  );
}
