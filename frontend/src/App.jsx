import { Outlet, Link, useLocation } from "react-router";
import { ArrowUpRight } from "lucide-react";

const NAV_LINKS = [
  { to: "/",              label: "00. Blueprint" },
  { to: "/library",       label: "01. Library" },
  { to: "/chat",          label: "02. Chat" },
  { to: "/memory",        label: "03. Memory" },
  { to: "/contradictions",label: "04. Clashes" },
];

function isActive(path, location) {
  if (path === "/") return location.pathname === "/";
  return location.pathname.startsWith(path);
}

export default function App() {
  const location = useLocation();
  const onLanding = location.pathname === "/";

  return (
    <div style={{ minHeight: "100vh", position: "relative" }}>

      {/* ── Navbar ────────────────────────────────────────────────────── */}
      <nav
        style={{
          backgroundColor: "#ffffff",
          borderBottom: "var(--border-thick)",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        <div
          className="brutalist-container"
          style={{
            height: "68px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          {/* Logo + wordmark */}
          <Link
            to="/"
            style={{
              textDecoration: "none",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              flexShrink: 0,
            }}
          >
            <img
              src="/logo.png"
              alt="PaperPlanes Logo"
              style={{
                height: "32px",
                display: "block",
                border: "var(--border-thin)",
                backgroundColor: "#ffffff",
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 800,
                fontSize: "1.15rem",
                color: "var(--fg-navy)",
                letterSpacing: "-0.02em",
              }}
            >
              PAPERPLANES
            </span>
          </Link>

          {/* Nav links */}
          <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
            {NAV_LINKS.map(({ to, label }) => {
              const active = isActive(to, location);
              return (
                <Link
                  key={to}
                  to={to}
                  className="mono-upper"
                  style={{
                    textDecoration: "none",
                    padding: "6px 12px",
                    color: active ? "var(--accent-cobalt)" : "var(--fg-navy)",
                    borderBottom: active
                      ? "2px solid var(--accent-cobalt)"
                      : "2px solid transparent",
                    transition: "all 160ms ease",
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    letterSpacing: "0.07em",
                  }}
                >
                  {label}
                </Link>
              );
            })}

            <Link
              to="/library"
              className="brutalist-btn brutalist-btn-primary brutalist-btn-sm"
              style={{ marginLeft: "8px", textDecoration: "none" }}
            >
              Scan Paper <ArrowUpRight size={13} />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Page content ─────────────────────────────────────────────── */}
      <main>
        <Outlet />
      </main>

      {/* ── Footer: full CTA on landing, minimal everywhere else ──────── */}
      {onLanding ? (
        <footer
          style={{
            backgroundColor: "var(--fg-navy)",
            color: "var(--bg-cream)",
            padding: "var(--space-xl) 0",
            borderTop: "var(--border-thick)",
            textAlign: "center",
            position: "relative",
          }}
        >
          <div className="brutalist-container">
            <h2
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: "-0.03em",
                fontSize: "clamp(2rem, 4vw, 3.2rem)",
                color: "#ffffff",
                marginBottom: "var(--space-sm)",
                lineHeight: 0.95,
              }}
            >
              INGEST LITERATURE NOW.
            </h2>
            <p
              style={{
                color: "#a4acc2",
                marginBottom: "var(--space-md)",
                maxWidth: "520px",
                margin: "0 auto var(--space-md) auto",
                fontSize: "1rem",
                lineHeight: 1.6,
              }}
            >
              Spin up the CockroachDB backend, load your AWS Bedrock credentials,
              and watch the agent resolve conflicting facts in real time.
            </p>
            <Link
              to="/library"
              className="brutalist-btn brutalist-btn-primary"
              style={{ border: "4px solid #ffffff", color: "#ffffff", textDecoration: "none" }}
            >
              Launch Ingestion Console
            </Link>
            <div
              className="mono-upper"
              style={{
                marginTop: "var(--space-xl)",
                borderTop: "1px solid rgba(164,172,194,0.15)",
                paddingTop: "var(--space-md)",
                color: "#a4acc2",
                fontSize: "0.65rem",
              }}
            >
              PAPERPLANES // COCKROACHDB × AWS AGENTIC MEMORY ENGINE // 2026
            </div>
          </div>
        </footer>
      ) : (
        <footer
          style={{
            borderTop: "1px solid var(--border-ui)",
            padding: "var(--space-md) 0",
            backgroundColor: "var(--bg-cream)",
          }}
        >
          <div
            className="brutalist-container mono"
            style={{ color: "var(--fg-muted)", fontSize: "0.75rem", textAlign: "center" }}
          >
            PaperPlanes — CockroachDB × AWS Agentic Memory Engine
          </div>
        </footer>
      )}
    </div>
  );
}
