import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Grip, Leaf, Maximize2, Minus, X } from "lucide-react";
import { Link } from "react-router-dom";
import "./assistant.css";
const Chat = lazy(() =>
  import("./AssistantChat").then((m) => ({ default: m.AssistantChat })),
);
const positionKey = "skyview-mitra-node-position";
export function FloatingAssistant() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [position, setPosition] = useState(() => {
    try {
      const p = JSON.parse(localStorage.getItem(positionKey) || "null");
      if (Number.isFinite(p?.x) && Number.isFinite(p?.y)) return p;
    } catch {}
    return { x: 24, y: Math.max(20, window.innerHeight - 610) };
  });
  const node = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    x: number;
    y: number;
    startX: number;
    startY: number;
  } | null>(null);
  const clamp = (x: number, y: number) => ({
    x: Math.max(
      8,
      Math.min(x, window.innerWidth - (node.current?.offsetWidth || 380) - 8),
    ),
    y: Math.max(
      8,
      Math.min(y, window.innerHeight - (node.current?.offsetHeight || 54) - 8),
    ),
  });
  useEffect(() => {
    const resize = () =>
      setPosition((p) => {
        const next = clamp(p.x, p.y);
        return next.x === p.x && next.y === p.y ? p : next;
      });
    window.addEventListener("resize", resize);
    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    if (node.current) observer?.observe(node.current);
    if (open) resize();
    return () => {
      window.removeEventListener("resize", resize);
      observer?.disconnect();
    };
  }, [open, minimized]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        localStorage.setItem(positionKey, JSON.stringify(position));
      } catch {

      }
    }, 250);
    return () => clearTimeout(timer);
  }, [position]);
  if (!open)
    return (
      <button className="mitra-launcher" onClick={() => setOpen(true)}>
        <span>
          <Leaf size={18} />
        </span>
        Ask Mitra <span className="launcher-hint">Your farm companion</span>
      </button>
    );
  return (
    <div
      ref={node}
      className={`mitra-floating ${minimized ? "minimized" : ""}`}
      style={{ left: position.x, top: position.y }}
    >
      <header
        className="mitra-drag-bar"
        tabIndex={0}
        aria-label="Move assistant window using arrow keys or drag"
        onKeyDown={(e) => {
          if (
            ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)
          ) {
            e.preventDefault();
            setPosition((p) =>
              clamp(
                p.x +
                  (e.key === "ArrowLeft"
                    ? -20
                    : e.key === "ArrowRight"
                      ? 20
                      : 0),
                p.y +
                  (e.key === "ArrowUp" ? -20 : e.key === "ArrowDown" ? 20 : 0),
              ),
            );
          }
        }}
        onPointerDown={(e) => {
          if ((e.target as HTMLElement).closest("button,a")) return;
          drag.current = {
            x: e.clientX,
            y: e.clientY,
            startX: position.x,
            startY: position.y,
          };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (drag.current)
            setPosition(
              clamp(
                drag.current.startX + e.clientX - drag.current.x,
                drag.current.startY + e.clientY - drag.current.y,
              ),
            );
        }}
        onPointerUp={(e) => {
          if (drag.current) {
            localStorage.setItem(positionKey, JSON.stringify(position));
            drag.current = null;
            e.currentTarget.releasePointerCapture(e.pointerId);
          }
        }}
        onPointerCancel={() => {
          drag.current = null;
        }}
      >
        <Grip size={14} />
        <span className="floating-avatar">
          <Leaf size={15} />
        </span>
        <div>
          <strong>Kisan Mitra</strong>
          <small>Here to help you get it done</small>
        </div>
        <Link
          to="/workspace?view=chat"
          title="Open full assistant"
          aria-label="Open full assistant"
        >
          <Maximize2 size={13} />
        </Link>
        <button
          onClick={() => setMinimized((v) => !v)}
          aria-label={minimized ? "Expand assistant" : "Minimize assistant"}
        >
          <Minus size={14} />
        </button>
        <button onClick={() => setOpen(false)} aria-label="Close assistant">
          <X size={14} />
        </button>
      </header>
      {!minimized && (
        <Suspense
          fallback={
            <div className="mitra-loading">Opening your companion…</div>
          }
        >
          <Chat compact context="station" />
        </Suspense>
      )}
    </div>
  );
}
