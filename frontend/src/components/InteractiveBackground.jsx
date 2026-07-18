import { useEffect, useRef } from "react";

/**
 * High-performance ambient 3D particle network background component.
 * Uses canvas rendering to draw orbiting node connections that react to mouse distance.
 */
export default function InteractiveBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let animationFrameId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const particles = [];
    // Dynamic particle density based on screen dimensions
    const particleCount = Math.min(65, Math.floor((width * height) / 24000));
    const connectionDistance = 110;
    const mouse = { x: null, y: null, radius: 140 };

    // Respect system reduced motion preferences
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Fetch theme accent color variables dynamically
    const getThemeColors = () => {
      const style = getComputedStyle(document.documentElement);
      const accent = style.getPropertyValue("--accent").trim() || "#7c9cff";
      return { accent };
    };

    let colors = getThemeColors();

    class Particle {
      constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        // Simulated depth layer (Z-axis scaling factor)
        this.z = Math.random() * 1.6 + 0.4;
        this.baseSpeedX = (Math.random() - 0.5) * 0.35;
        this.baseSpeedY = (Math.random() - 0.5) * 0.35;
        this.vx = this.baseSpeedX;
        this.vy = this.baseSpeedY;
        this.radius = Math.random() * 1.5 + 1;
      }

      update() {
        if (prefersReducedMotion) return;

        // Base drift speed divided by depth to create a parallax illusion
        this.x += this.vx / this.z;
        this.y += this.vy / this.z;

        // Bound collisions
        if (this.x < 0 || this.x > width) this.vx = -this.vx;
        if (this.y < 0 || this.y > height) this.vy = -this.vy;

        // Interactive mouse attraction
        if (mouse.x !== null && mouse.y !== null) {
          const dx = mouse.x - this.x;
          const dy = mouse.y - this.y;
          const dist = Math.hypot(dx, dy);

          if (dist < mouse.radius) {
            const force = (mouse.radius - dist) / mouse.radius;
            const angle = Math.atan2(dy, dx);
            // Slowly attract particles
            this.x += Math.cos(angle) * force * 0.4;
            this.y += Math.sin(angle) * force * 0.4;
          }
        }
      }

      draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius * this.z, 0, Math.PI * 2);
        // Fade opacity based on Z depth layer
        const hexAlpha = Math.floor(Math.min(1, this.z / 2) * 55).toString(16).padStart(2, "0");
        ctx.fillStyle = colors.accent + hexAlpha;
        ctx.fill();
      }
    }

    // Spawn particle cluster
    for (let i = 0; i < particleCount; i++) {
      particles.push(new Particle());
    }

    const handleMouseMove = (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };

    const handleMouseLeave = () => {
      mouse.x = null;
      mouse.y = null;
    };

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);
    window.addEventListener("resize", handleResize);

    // Watch for class list changes (theme switching)
    const observer = new MutationObserver(() => {
      colors = getThemeColors();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "class"],
    });

    const getRgbFromHex = (hex) => {
      if (!hex.startsWith("#")) return "124, 156, 255";
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      return `${r}, ${g}, ${b}`;
    };

    const animate = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw networks
      const rgb = getRgbFromHex(colors.accent);
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const p1 = particles[i];
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.hypot(dx, dy);

          if (dist < connectionDistance) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            // Compute line opacity dynamically based on depth + distance
            const alpha = (
              ((connectionDistance - dist) / connectionDistance) *
              0.08 *
              (p1.z * p2.z) / 4
            ).toFixed(3);
            ctx.strokeStyle = `rgba(${rgb}, ${alpha})`;
            ctx.lineWidth = 0.45 * p1.z;
            ctx.stroke();
          }
        }
      }

      // Render dots
      particles.forEach((p) => {
        p.update();
        p.draw();
      });

      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
      window.removeEventListener("resize", handleResize);
      observer.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: -1,
        pointerEvents: "none",
        opacity: 0.7,
      }}
    />
  );
}
