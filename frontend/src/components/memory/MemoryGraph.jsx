import { useEffect, useRef, useState } from "react";
import { Network } from "lucide-react";

/**
 * Interactive visual Local Neighborhood Memory Graph.
 * Renders the active selected note at the center and orbiting linked satellite nodes.
 * Hovering shows a tooltip. Clicking a satellite re-centers it.
 */
export default function MemoryGraph({ note, onOpenNote }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let animationFrameId;

    const resizeCanvas = () => {
      if (containerRef.current) {
        canvas.width = containerRef.current.clientWidth;
        canvas.height = 240;
      }
    };
    resizeCanvas();

    let width = canvas.width;
    let height = canvas.height;

    let nodes = [];
    let connections = [];

    const getThemeColors = () => {
      const style = getComputedStyle(document.documentElement);
      return {
        accent: style.getPropertyValue("--accent").trim() || "#7c9cff",
        danger: style.getPropertyValue("--danger").trim() || "#f87171",
        info: style.getPropertyValue("--info").trim() || "#60c4ff",
        textPrimary: style.getPropertyValue("--text-primary").trim() || "#e9ecf5",
        textSecondary: style.getPropertyValue("--text-secondary").trim() || "#a4acc2",
        bgSurface: style.getPropertyValue("--bg-surface-raised").trim() || "#191d27",
        borderSubtle: style.getPropertyValue("--border-subtle").trim() || "#232837",
      };
    };

    let colors = getThemeColors();

    const buildGraph = () => {
      if (!note) return;

      const newNodes = [];
      const newConnections = [];

      // Center Node (selected note)
      const centerNode = {
        id: note.id,
        content: note.content,
        isCenter: true,
        x: width / 2,
        y: height / 2,
        targetX: width / 2,
        targetY: height / 2,
        radius: 32,
        status: note.status,
        color: colors.accent,
        floatOffset: Math.random() * 100,
      };
      newNodes.push(centerNode);

      // Satellite Nodes (linked notes)
      const links = note.links || [];
      const count = links.length;
      const radius = 90; // orbit distance

      links.forEach((link, idx) => {
        const angle = (idx * 2 * Math.PI) / count + Math.PI / 4;
        const satelliteId = link.other?.id;
        const isContradiction = link.relation_type === "contradicts";

        const satNode = {
          id: satelliteId,
          content: link.other?.content || "Linked Memory",
          isCenter: false,
          x: width / 2 + Math.cos(angle) * radius,
          y: height / 2 + Math.sin(angle) * radius,
          targetX: width / 2 + Math.cos(angle) * radius,
          targetY: height / 2 + Math.sin(angle) * radius,
          radius: 20,
          status: link.other?.status,
          relation: link.relation_type,
          direction: link.direction,
          color: isContradiction ? colors.danger : colors.info,
          floatOffset: Math.random() * 100 + (idx + 1) * 20,
        };
        newNodes.push(satNode);

        newConnections.push({
          from: centerNode,
          to: satNode,
          relation: link.relation_type,
          direction: link.direction,
          isContradiction,
        });
      });

      nodes = newNodes;
      connections = newConnections;
    };

    buildGraph();

    let mouseX = null;
    let mouseY = null;

    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;

      let foundHover = null;
      for (const node of nodes) {
        const dist = Math.hypot(node.x - mouseX, node.y - mouseY);
        if (dist < node.radius + 10) {
          foundHover = node;
          break;
        }
      }
      if (foundHover !== hoveredNode) {
        setHoveredNode(foundHover);
        canvas.style.cursor = foundHover ? "pointer" : "default";
      }
    };

    const handleMouseLeave = () => {
      mouseX = null;
      mouseY = null;
      setHoveredNode(null);
      canvas.style.cursor = "default";
    };

    const handleMouseClick = () => {
      if (hoveredNode && !hoveredNode.isCenter && hoveredNode.id) {
        onOpenNote(hoveredNode.id);
      }
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);
    canvas.addEventListener("click", handleMouseClick);

    // Watch for theme modifications
    const observer = new MutationObserver(() => {
      colors = getThemeColors();
      buildGraph();
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });

    let time = 0;

    const render = () => {
      time += 0.012;
      ctx.clearRect(0, 0, width, height);

      // Connection lines
      connections.forEach((conn) => {
        ctx.beginPath();
        ctx.moveTo(conn.from.x, conn.from.y);
        ctx.lineTo(conn.to.x, conn.to.y);
        ctx.strokeStyle = conn.isContradiction ? `${colors.danger}60` : `${colors.borderSubtle}cc`;
        ctx.lineWidth = conn.isContradiction ? 2.5 : 1.1;
        ctx.stroke();

        // Relation label badge
        const midX = (conn.from.x + conn.to.x) / 2;
        const midY = (conn.from.y + conn.to.y) / 2;
        
        ctx.save();
        ctx.translate(midX, midY);
        const angle = Math.atan2(conn.to.y - conn.from.y, conn.to.x - conn.from.x);
        ctx.rotate(Math.abs(angle) > Math.PI / 2 ? angle + Math.PI : angle);

        ctx.beginPath();
        const text = conn.relation;
        ctx.font = "bold 8.5px var(--font-mono)";
        const textWidth = ctx.measureText(text).width;
        ctx.roundRect(-textWidth / 2 - 4, -6, textWidth + 8, 12, 3);
        ctx.fillStyle = colors.bgSurface;
        ctx.strokeStyle = conn.isContradiction ? colors.danger : colors.borderSubtle;
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = conn.isContradiction ? colors.danger : colors.textSecondary;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, 0, 0);
        ctx.restore();
      });

      // Update orbits and draw nodes
      nodes.forEach((node) => {
        if (!node.isCenter) {
          const driftRadius = 2.5;
          node.x = node.targetX + Math.sin(time + node.floatOffset) * driftRadius;
          node.y = node.targetY + Math.cos(time * 0.85 + node.floatOffset) * driftRadius;
        } else {
          node.x = node.targetX + Math.sin(time * 0.8) * 0.6;
          node.y = node.targetY + Math.cos(time * 0.4) * 0.6;
        }

        const isHovered = hoveredNode && hoveredNode.id === node.id;
        const scale = isHovered ? 1.12 : 1.0;
        const currentRadius = node.radius * scale;

        // Shadow radial glow
        const glowGrd = ctx.createRadialGradient(node.x, node.y, currentRadius - 4, node.x, node.y, currentRadius + 10);
        glowGrd.addColorStop(0, `${node.color}25`);
        glowGrd.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = glowGrd;
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentRadius + 10, 0, Math.PI * 2);
        ctx.fill();

        // Circle body
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentRadius, 0, Math.PI * 2);
        ctx.fillStyle = colors.bgSurface;
        ctx.strokeStyle = isHovered ? colors.textPrimary : node.color;
        ctx.lineWidth = isHovered ? 2.5 : 1.8;
        ctx.fill();
        ctx.stroke();

        // Core dot
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.isCenter ? 5 : 3.5, 0, Math.PI * 2);
        ctx.fillStyle = node.color;
        ctx.fill();

        // Note labels
        ctx.fillStyle = colors.textPrimary;
        ctx.textAlign = "center";
        ctx.font = node.isCenter ? "bold 10px var(--font-sans)" : "9px var(--font-sans)";
        
        const labelText = node.isCenter ? "Active Memory" : node.content.slice(0, 14) + "...";
        ctx.fillText(labelText, node.x, node.y + currentRadius + 12);
      });

      // Tooltip overlays
      if (hoveredNode) {
        ctx.save();
        const padding = 7;
        const maxTooltipWidth = 190;
        const text = hoveredNode.content;
        
        ctx.font = "10.5px var(--font-sans)";
        const words = text.split(" ");
        let line = "";
        const lines = [];
        for (let n = 0; n < words.length; n++) {
          const testLine = line + words[n] + " ";
          const metrics = ctx.measureText(testLine);
          if (metrics.width > maxTooltipWidth - padding * 2 && n > 0) {
            lines.push(line);
            line = words[n] + " ";
          } else {
            line = testLine;
          }
        }
        lines.push(line);

        const tooltipHeight = lines.length * 14 + padding * 2;
        const tooltipX = Math.max(10, Math.min(width - maxTooltipWidth - 10, hoveredNode.x - maxTooltipWidth / 2));
        const tooltipY = hoveredNode.y - hoveredNode.radius - tooltipHeight - 12 > 10 
          ? hoveredNode.y - hoveredNode.radius - tooltipHeight - 6 
          : hoveredNode.y + hoveredNode.radius + 6;

        ctx.beginPath();
        ctx.roundRect(tooltipX, tooltipY, maxTooltipWidth, tooltipHeight, 5);
        ctx.fillStyle = "rgba(18, 21, 28, 0.95)";
        ctx.strokeStyle = hoveredNode.color;
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = colors.textPrimary;
        ctx.textAlign = "left";
        lines.forEach((l, index) => {
          ctx.fillText(l.trim(), tooltipX + padding, tooltipY + padding + index * 14 + 10);
        });
        ctx.restore();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    const handleResize = () => {
      resizeCanvas();
      width = canvas.width;
      height = canvas.height;
      buildGraph();
    };

    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
      canvas.removeEventListener("click", handleMouseClick);
      window.removeEventListener("resize", handleResize);
      observer.disconnect();
    };
  }, [note, hoveredNode, onOpenNote]);

  return (
    <div
      ref={containerRef}
      className="glass-panel"
      style={{
        width: "100%",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
        position: "relative",
        marginBottom: "var(--space-4)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: "10px",
          left: "12px",
          display: "flex",
          alignItems: "center",
          gap: "6px",
          zIndex: 10,
          fontSize: "11px",
          fontWeight: "600",
          color: "var(--text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.03em",
        }}
      >
        <Network size={12} style={{ color: "var(--accent)" }} />
        Memory Neighborhood
      </div>

      {note?.links?.length === 0 && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "var(--space-4)",
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          <div className="text-muted" style={{ fontSize: "12px" }}>
            This memory stands alone. Link relationships will render as they are extracted.
          </div>
        </div>
      )}

      <canvas ref={canvasRef} style={{ display: "block" }} />
    </div>
  );
}
