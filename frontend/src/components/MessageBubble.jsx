import { useState } from "react";
import { User, Sparkles, Copy, Check } from "lucide-react";
import CitationChips from "./CitationChips.jsx";
import MemoryCitationChips from "./MemoryCitationChips.jsx";

function formatTime(isoString) {
  if (!isoString) return "";
  try {
    return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function parseInlineFormatting(text) {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={idx}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

function parseMarkdown(text) {
  if (!text) return "";
  
  const parts = text.split(/(```[\s\S]*?```)/g);
  
  return parts.map((part, idx) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      const match = part.match(/```(\w*)\n([\s\S]*?)```/);
      const language = match ? match[1] : "";
      const code = match ? match[2] : part.slice(3, -3);
      return (
        <pre key={idx} style={{ 
          backgroundColor: "#101b3a", 
          color: "#a4acc2", 
          padding: "var(--space-sm)", 
          borderRadius: "4px",
          overflowX: "auto",
          marginTop: "8px",
          border: "var(--border-thin)"
        }} className="mono">
          {language && (
            <div style={{ fontSize: "10px", textTransform: "uppercase", opacity: 0.6, marginBottom: "4px" }}>
              {language}
            </div>
          )}
          <code style={{ fontSize: "0.8rem", textTransform: "none", letterSpacing: "normal" }}>{code.trim()}</code>
        </pre>
      );
    }
    
    const lines = part.split("\n");
    const resultElements = [];
    let currentList = [];
    
    lines.forEach((line, lineIdx) => {
      const listMatch = line.match(/^[\s]*[-*+]\s+(.*)/);
      if (listMatch) {
        currentList.push(listMatch[1]);
      } else {
        if (currentList.length > 0) {
          resultElements.push(
            <ul key={`ul-${lineIdx}`} style={{ paddingLeft: "20px", marginBottom: "8px" }}>
              {currentList.map((item, itemIdx) => (
                <li key={itemIdx} style={{ marginBottom: "4px" }}>{parseInlineFormatting(item)}</li>
              ))}
            </ul>
          );
          currentList = [];
        }
        
        if (line.trim() !== "") {
          resultElements.push(<p key={lineIdx} style={{ marginBottom: "8px" }}>{parseInlineFormatting(line)}</p>);
        }
      }
    });
    
    if (currentList.length > 0) {
      resultElements.push(
        <ul key={`ul-end-${idx}`} style={{ paddingLeft: "20px", marginBottom: "8px" }}>
          {currentList.map((item, itemIdx) => (
            <li key={itemIdx} style={{ marginBottom: "4px" }}>{parseInlineFormatting(item)}</li>
          ))}
        </ul>
      );
    }
    
    return <span key={idx}>{resultElements}</span>;
  });
}

export default function MessageBubble({
  role,
  content,
  createdAt,
  citations,
  memoryCitations,
  pending = false,
}) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (pending || !content) return;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ 
      display: "flex", 
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "var(--space-md)",
      width: "100%"
    }}>
      <div 
        style={{ 
          maxWidth: "80%",
          backgroundColor: isUser ? "var(--bg-cream)" : "var(--bg-card)",
          border: isUser ? "1px solid var(--border-ui)" : "1px solid var(--border-ui)",
          borderLeft: isUser ? "1px solid var(--border-ui)" : "3px solid var(--accent-cobalt)",
          borderRadius: "6px",
          padding: "var(--space-sm)",
          display: "flex",
          gap: "var(--space-sm)",
          position: "relative",
          boxShadow: "var(--shadow-card)"
        }}
      >
        <span 
          style={{ 
            display: "inline-flex", 
            justifyContent: "center", 
            alignItems: "center", 
            width: "28px", 
            height: "28px", 
            borderRadius: "50%", 
            backgroundColor: isUser ? "var(--bg-cream)" : "#e8eeff", 
            color: isUser ? "var(--fg-navy)" : "var(--accent-cobalt)",
            flexShrink: 0
          }}
          aria-hidden="true"
        >
          {isUser ? <User size={14} /> : <Sparkles size={14} />}
        </span>

        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <div 
            className={isUser ? "" : "serif"}
            style={{ 
              fontSize: "1.05rem", 
              lineHeight: 1.5,
              color: "var(--fg-navy)"
            }}
          >
            {pending ? (
              <span style={{ display: "inline-flex", gap: "4px", padding: "8px 0" }}>
                <span className="dot-bounce" style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "var(--fg-navy)", animation: "bounce 1.4s infinite ease-in-out both" }} />
                <span className="dot-bounce" style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "var(--fg-navy)", animation: "bounce 1.4s infinite ease-in-out both 0.2s" }} />
                <span className="dot-bounce" style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "var(--fg-navy)", animation: "bounce 1.4s infinite ease-in-out both 0.4s" }} />
              </span>
            ) : isUser ? (
              content
            ) : (
              parseMarkdown(content)
            )}
          </div>

          {!pending && !isUser && <CitationChips citations={citations} />}
          {!pending && !isUser && <MemoryCitationChips citations={memoryCitations} />}
          
          {createdAt && !pending && (
            <div className="mono text-muted" style={{ fontSize: "0.7rem", marginTop: "8px" }}>
              {formatTime(createdAt)}
            </div>
          )}
        </div>
        
        {!pending && (
          <div style={{ alignSelf: "flex-start" }}>
            <button
              type="button"
              style={{
                padding: "4px",
                border: "none",
                background: "transparent",
                color: "var(--fg-muted)",
                cursor: "pointer"
              }}
              onClick={handleCopy}
              title="Copy to clipboard"
            >
              {copied ? <Check size={12} className="text-success" style={{ color: "var(--accent-green)" }} /> : <Copy size={12} />}
            </button>
          </div>
        )}
      </div>

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1.0); }
        }
      `}</style>
    </div>
  );
}
