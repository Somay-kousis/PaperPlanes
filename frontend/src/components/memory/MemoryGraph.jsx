import { useEffect, useRef, useState } from "react";
import { Network } from "lucide-react";

export default function MemoryGraph({ note, onOpenNote }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let animationFrameId;
    let currentHoveredNode = null;

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
      return {
        accent: "#0e46ec",      // Cobalt
        danger: "#ff3b30",      // Red
        info: "#ffd300",        // Yellow
        textPrimary: "#101b3a", // Navy
        textSecondary: "#6c757d",
        bgSurface: "#faf8f2",   // Warm cream
        borderSubtle: "#e0ddd4",// Warm border-ui
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
        radius: 30,
        status: note.status,
        color: colors.accent,
        floatOffset: Math.random() * 100,
      };
      newNodes.push(centerNode);

      // Satellite Nodes (linked notes)
      const links = note.links || [];
      const count = links.length;
      const radius = 85; // orbit distance

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
          radius: 18,
          status: link.other?.status,
          relation: link.relation_type,
          direction: link.direction,
          color: isContradiction ? colors.danger : "#6c757d",
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
        if (dist < node.radius + 6) {
          foundHover = node;
          break;
        }
      }
      if (foundHover !== currentHoveredNode) {
        currentHoveredNode = foundHover;
        canvas.style.cursor = foundHover ? "pointer" : "default";
      }
    };

    const handleMouseLeave = () => {
      mouseX = null;
      mouseY = null;
      currentHoveredNode = null;
      canvas.style.cursor = "default";
    };

    const handleMouseClick = () => {
      if (currentHoveredNode && !currentHoveredNode.isCenter && currentHoveredNode.id) {
        onOpenNote(currentHoveredNode.id);
      }
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mouseleave", handleMouseLeave);
    canvas.addEventListener("click", handleMouseClick);

    let time = 0;

    const render = () => {
      time += 0.01;
      ctx.clearRect(0, 0, width, height);

      // Connection lines
      connections.forEach((conn) => {
        ctx.beginPath();
        ctx.moveTo(conn.from.x, conn.from.y);
        ctx.lineTo(conn.to.x, conn.to.y);
        ctx.strokeStyle = conn.isContradiction ? `${colors.danger}60` : `${colors.borderSubtle}bb`;
        ctx.lineWidth = conn.isContradiction ? 2 : 1;
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
        ctx.font = "bold 8px monospace";
        const textWidth = ctx.measureText(text).width;
        
        // rounded rectangle
        ctx.roundRect(-textWidth / 2 - 4, -5, textWidth + 8, 10, 2);
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
          const driftRadius = 2;
          node.x = node.targetX + Math.sin(time + node.floatOffset) * driftRadius;
          node.y = node.targetY + Math.cos(time * 0.8 + node.floatOffset) * driftRadius;
        } else {
          node.x = node.targetX + Math.sin(time * 0.8) * 0.4;
          node.y = node.targetY + Math.cos(time * 0.4) * 0.4;
        }

        const isHovered = currentHoveredNode && currentHoveredNode.id === node.id;
        const scale = isHovered ? 1.1 : 1.0;
        const currentRadius = node.radius * scale;

        // Circle body
        ctx.beginPath();
        ctx.arc(node.x, node.y, currentRadius, 0, Math.PI * 2);
        ctx.fillStyle = colors.bgSurface;
        ctx.strokeStyle = isHovered ? colors.textPrimary : node.color;
        ctx.lineWidth = isHovered ? 2 : 1.5;
        ctx.fill();
        ctx.stroke();

        // Core dot
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.isCenter ? 4 : 3, 0, Math.PI * 2);
        ctx.fillStyle = node.color;
        ctx.fill();

        // Note labels
        ctx.fillStyle = colors.textPrimary;
        ctx.textAlign = "center";
        ctx.font = node.isCenter ? "bold 9px sans-serif" : "8px sans-serif";
        
        const labelText = node.isCenter ? "Active Fact" : node.content.slice(0, 12) + "...";
        ctx.fillText(labelText, node.x, node.y + currentRadius + 10);
      });

      // Tooltip overlays
      if (currentHoveredNode) {
        ctx.save();
        const padding = 6;
        const maxTooltipWidth = 180;
        const text = currentHoveredNode.content;
        
        ctx.font = "10px sans-serif";
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

        const tooltipHeight = lines.length * 13 + padding * 2;
        const tooltipX = Math.max(10, Math.min(width - maxTooltipWidth - 10, currentHoveredNode.x - maxTooltipWidth / 2));
        const tooltipY = currentHoveredNode.y - currentHoveredNode.radius - tooltipHeight - 10 > 10 
          ? currentHoveredNode.y - currentHoveredNode.radius - tooltipHeight - 4 
          : currentHoveredNode.y + currentHoveredNode.radius + 4;

        ctx.beginPath();
        ctx.roundRect(tooltipX, tooltipY, maxTooltipWidth, tooltipHeight, 4);
        ctx.fillStyle = "rgba(16, 27, 58, 0.95)";
        ctx.strokeStyle = currentHoveredNode.color;
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "left";
        lines.forEach((l, index) => {
          ctx.fillText(l.trim(), tooltipX + padding, tooltipY + padding + index * 13 + 8);
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
    };
  }, [note, onOpenNote]);

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        border: "1px solid var(--border-ui)",
        borderRadius: "5px",
        overflow: "hidden",
        position: "relative",
        marginBottom: "var(--space-sm)",
        backgroundColor: "var(--bg-cream)",
        height: "240px"
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
          color: "var(--fg-muted)"
        }}
        className="mono"
      >
        <Network size={12} style={{ color: "var(--accent-cobalt)" }} />
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
            padding: "var(--space-sm)",
            textAlign: "center",
            pointerEvents: "none"
          }}
        >
          <div className="mono text-muted" style={{ fontSize: "12px" }}>
            This memory stands alone. No active links currently resolved.
          </div>
        </div>
      )}

      <canvas ref={canvasRef} style={{ display: "block" }} />
    </div>
  );
}
