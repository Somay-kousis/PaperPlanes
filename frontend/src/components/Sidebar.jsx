import { useState, useEffect } from "react";
import { NavLink } from "react-router";
import { MessageSquare, Library, Brain, GitCompareArrows, Send, Sun, Moon } from "lucide-react";

const NAV_ITEMS = [
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/library", label: "Library", icon: Library },
  { to: "/memory", label: "Memory", icon: Brain },
  { to: "/contradictions", label: "Contradictions", icon: GitCompareArrows },
];

export default function Sidebar() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  });

  useEffect(() => {
    if (theme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark">
          <Send size={16} strokeWidth={2.25} />
        </span>
        <span className="sidebar-brand-text">
          PaperPlanes
          <small>Research Companion</small>
        </span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            <Icon size={16} strokeWidth={2} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot" aria-hidden="true" />
        API: /api
      </div>

      <div className="theme-toggle-container">
        <button type="button" className="theme-toggle-btn" onClick={toggleTheme}>
          <span>Appearance</span>
          {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}
        </button>
      </div>
    </aside>
  );
}

