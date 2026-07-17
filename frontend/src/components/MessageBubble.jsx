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
        <pre key={idx}>
          {language && (
            <div style={{ fontSize: "10px", textTransform: "uppercase", color: "var(--text-tertiary)", marginBottom: "4px" }}>
              {language}
            </div>
          )}
          <code>{code.trim()}</code>
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
            <ul key={`ul-${lineIdx}`}>
              {currentList.map((item, itemIdx) => (
                <li key={itemIdx}>{parseInlineFormatting(item)}</li>
              ))}
            </ul>
          );
          currentList = [];
        }
        
        if (line.trim() !== "") {
          resultElements.push(<p key={lineIdx}>{parseInlineFormatting(line)}</p>);
        }
      }
    });
    
    if (currentList.length > 0) {
      resultElements.push(
        <ul key={`ul-end-${idx}`}>
          {currentList.map((item, itemIdx) => (
            <li key={itemIdx}>{parseInlineFormatting(item)}</li>
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
    <div className="message-bubble-container">
      <div className={"message-bubble" + (isUser ? " from-user" : "")}>
        <span className="message-avatar" aria-hidden="true">
          {isUser ? <User size={14} /> : <Sparkles size={14} />}
        </span>
        <div className="message-bubble-wrapper">
          <div>
            <div className="message-content">
              {pending ? (
                <span className="typing-indicator" aria-label="Assistant is typing">
                  <span />
                  <span />
                  <span />
                </span>
              ) : isUser ? (
                content
              ) : (
                parseMarkdown(content)
              )}
            </div>
            {!pending && !isUser && <CitationChips citations={citations} />}
            {!pending && !isUser && <MemoryCitationChips citations={memoryCitations} />}
            {createdAt && !pending && <div className="message-meta">{formatTime(createdAt)}</div>}
          </div>
          
          {!pending && (
            <div className="message-actions">
              <button
                type="button"
                className="btn-copy"
                onClick={handleCopy}
                title="Copy to clipboard"
              >
                {copied ? <Check size={12} className="text-success" /> : <Copy size={12} />}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
