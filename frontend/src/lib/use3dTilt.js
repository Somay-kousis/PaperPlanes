import { useRef } from "react";

/**
 * Custom React hook for adding a high-performance 3D tilt effect to components.
 * Calculates cursor coordinates relative to the card's center and adjusts transform properties.
 *
 * @param {number} maxRotate Max rotation degrees (default: 8)
 * @param {number} scale Hover scale factor (default: 1.02)
 */
export default function use3dTilt(maxRotate = 8, scale = 1.02) {
  const elementRef = useRef(null);

  const handleMouseMove = (e) => {
    const el = elementRef.current || e.currentTarget;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    // Cursor position normalized from -0.5 to 0.5 relative to the element center
    const x = (e.clientX - rect.left) / width - 0.5;
    const y = (e.clientY - rect.top) / height - 0.5;

    // Calculate rotation angles
    const rotateX = -(y * maxRotate).toFixed(2);
    const rotateY = (x * maxRotate).toFixed(2);

    // Apply rotation and scale
    el.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(${scale}, ${scale}, ${scale})`;

    // Dynamic glare angle variable
    const glareX = ((x + 0.5) * 100).toFixed(1);
    const glareY = ((y + 0.5) * 100).toFixed(1);
    el.style.setProperty("--glare-pos", `${glareX}% ${glareY}%`);
  };

  const handleMouseLeave = (e) => {
    const el = elementRef.current || e.currentTarget;
    if (!el) return;

    el.style.transition = "transform 0.4s cubic-bezier(0.25, 1, 0.5, 1)";
    el.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
    el.style.setProperty("--glare-pos", "50% 50%");
  };

  const handleMouseEnter = (e) => {
    const el = elementRef.current || e.currentTarget;
    if (!el) return;
    
    el.style.transition = "transform 0.1s cubic-bezier(0.25, 1, 0.5, 1)";
  };

  return {
    ref: elementRef,
    onMouseMove: handleMouseMove,
    onMouseLeave: handleMouseLeave,
    onMouseEnter: handleMouseEnter,
  };
}
