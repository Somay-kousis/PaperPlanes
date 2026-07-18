import { AlertTriangle, X } from "lucide-react";

export default function ErrorBanner({ title = "Something went wrong", message, onDismiss = null }) {
  return (
    <div className="error-banner" role="alert">
      <AlertTriangle size={18} strokeWidth={2} style={{ flexShrink: 0, marginTop: 1 }} />
      <div className="error-banner-body">
        <div className="error-banner-title">{title}</div>
        {message && <div>{message}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          className="error-banner-close"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X size={16} />
        </button>
      )}
    </div>
  );
}
