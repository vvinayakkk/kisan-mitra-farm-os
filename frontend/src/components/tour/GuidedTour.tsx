import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Compass, X } from "lucide-react";
import { getAssistantSessionId } from "@/lib/assistantClient";
import "./tour.css";

export type TourStep = { target: string; title: string; body: string };
let activeTour: symbol | null = null;
type Rect = { x: number; y: number; width: number; height: number };
export function visibleTarget(selector: string): HTMLElement | undefined {
  return Array.from(document.querySelectorAll<HTMLElement>(selector)).find(el => {
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && !el.closest('[hidden]') && getComputedStyle(el).visibility !== 'hidden';
  });
}
function ownerKey(scope: string) {
  try {
    const owner = localStorage.getItem('firebase-session-uid') || getAssistantSessionId();
    return owner ? `mitra-tour-v1:${owner}:${scope}` : null;
  } catch { return null; }
}
export function tourPosition(rect: Rect, width: number, height: number, viewportWidth: number, viewportHeight: number) {
  const left = Math.max(12, Math.min(rect.x + rect.width / 2 - width / 2, viewportWidth - width - 12));
  const below = rect.y + rect.height + 16;
  const top = below + height <= viewportHeight - 12 ? below : rect.y - height - 16 >= 12 ? rect.y - height - 16 : Math.max(12, viewportHeight - height - 12);
  return { left, top };
}

/** Read-only tour: never clicks controls, submits forms, requests permissions or changes farm data. */
export function GuidedTour({ scope, steps, auto = true }: { scope: string; steps: TourStep[]; auto?: boolean }) {
  const key = ownerKey(scope);
  const token = useRef(Symbol(scope));
  const [index, setIndex] = useState<number | null>(null);
  const [rect, setRect] = useState<Rect | null>(null);
  const [size, setSize] = useState({ width: 320, height: 250 });
  const [viewport, setViewport] = useState({ width: innerWidth, height: innerHeight });
  const panel = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const id = useId().replace(/:/g, '');
  const current = index === null ? null : steps[index];
  function remember(value: string) { try { if (key) localStorage.setItem(key, value); } catch { /* Tours still work without browser storage. */ } }
  function close() { if (activeTour === token.current) activeTour = null; remember('done'); setIndex(null); setRect(null); requestAnimationFrame(() => { const target = previousFocus.current?.isConnected ? previousFocus.current : trigger.current; target?.focus({ preventScroll: true }); }); }
  function start() { if (activeTour && activeTour !== token.current) return; activeTour = token.current; previousFocus.current = document.activeElement as HTMLElement; setIndex(0); }
  useEffect(() => {
    setRect(null); setIndex(null);
    if (!auto || !key) return;
    let saved: string | null = null;
    try { saved = localStorage.getItem(key); } catch { return; }
    if (saved === 'done') return;
    const resume = Number(saved || 0);
    const timer = window.setTimeout(() => {
      // Do not interrupt a call, an editor, or another guide opened in the meantime.
      if (activeTour || visibleTarget('[role="dialog"], .live-conversation') || (scope !== 'companion' && visibleTarget('.saathi-panel'))) return;
      activeTour = token.current;
      previousFocus.current = document.activeElement as HTMLElement; setIndex(Number.isInteger(resume) && resume >= 0 && resume < steps.length ? resume : 0); }, 700);
    return () => clearTimeout(timer);
  }, [scope, key, auto]);
  useEffect(() => () => { if (activeTour === token.current) activeTour = null; }, []);
  useEffect(() => {
    if (index === null || !current) return;
    remember(String(index));
    setRect(null);
    let frame = 0, stopped = false, target: HTMLElement | undefined;
    const started = performance.now();
    const track = () => {
      if (stopped) return;
      const found = visibleTarget(current.target);
      if (!found) {
        setRect(null);
        if (performance.now() - started > 5000) { if (index + 1 < steps.length) setIndex(index + 1); else close(); return; }
      } else {
        if (found !== target) { target = found; found.scrollIntoView?.({ block: 'center', inline: 'nearest', behavior: 'instant' as ScrollBehavior }); }
        const r = found.getBoundingClientRect();
        const next = { x: Math.max(4, r.left - 5), y: Math.max(4, r.top - 5), width: Math.max(0, Math.min(innerWidth - 4, r.right + 5) - Math.max(4, r.left - 5)), height: Math.max(0, Math.min(innerHeight - 4, r.bottom + 5) - Math.max(4, r.top - 5)) };
        setRect(old => old && Object.keys(next).every(k => old[k as keyof Rect] === next[k as keyof Rect]) ? old : next);
      }
      frame = requestAnimationFrame(track);
    };
    frame = requestAnimationFrame(track);
    return () => { stopped = true; cancelAnimationFrame(frame); };
  }, [index, current?.target, scope]);
  useEffect(() => {
    if (index === null) return;
    const observer = new ResizeObserver(() => { const r = panel.current?.getBoundingClientRect(); if (r) setSize({ width: r.width, height: r.height }); });
    if (panel.current) observer.observe(panel.current);
    panel.current?.focus({ preventScroll: true });
    return () => observer.disconnect();
  }, [index, !!rect]);
  useEffect(() => {
    if (index === null) return;
    // Keep background controls out of keyboard and assistive-technology navigation.
    const roots = Array.from(document.body.children).filter((el): el is HTMLElement => el instanceof HTMLElement && !el.classList.contains('mitra-tour-layer') && !['SCRIPT', 'STYLE'].includes(el.tagName));
    const previous = roots.map(el => el.inert);
    roots.forEach(el => { el.inert = true; });
    const overflow = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    return () => { roots.forEach((el, i) => { el.inert = previous[i]; }); document.documentElement.style.overflow = overflow; };
  }, [index !== null]);
  useEffect(() => {
    const resize = () => setViewport({width: innerWidth, height: innerHeight});
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  const position = rect ? tourPosition(rect, size.width, size.height, viewport.width, viewport.height) : { left: 12, top: 12 };
  const endX = rect ? Math.max(rect.x + 6, Math.min(position.left + size.width / 2, rect.x + rect.width - 6)) : 0;
  const below = rect ? position.top >= rect.y + rect.height : true;
  return <>
    <button ref={trigger} className="mitra-tour-trigger" onClick={start} aria-label="Replay page tour"><Compass size={16}/><span>Take a tour</span></button>
    {index !== null && current && createPortal(<div className="mitra-tour-layer">
      <svg className="mitra-tour-shade" width="100%" height="100%" aria-hidden="true"><defs><mask id={id}><rect width="100%" height="100%" fill="white"/>{rect && <rect {...rect} rx="12" fill="black"/>}</mask></defs><rect width="100%" height="100%" fill="rgba(27,38,26,.48)" mask={`url(#${id})`}/>{rect && <><rect {...rect} rx="12" fill="none" stroke="#e4efbf" strokeWidth="3"/><path d={`M ${position.left + size.width / 2} ${below ? position.top : position.top + size.height} L ${endX} ${below ? rect.y + rect.height + 3 : rect.y - 3}`} stroke="#e4efbf" strokeWidth="3" fill="none"/></>}</svg>
      <div ref={panel} className="mitra-tour-card" style={position} role="dialog" aria-modal="true" aria-labelledby={`${id}-title`} aria-describedby={`${id}-body`} tabIndex={-1} onKeyDown={e => {
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
        if (e.key === 'Tab') { const controls = Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled)') || []); const first = controls[0], last = controls[controls.length - 1]; if (e.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) { e.preventDefault(); last?.focus(); } else if (!e.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) { e.preventDefault(); first?.focus(); } }
      }}>
        <div className="mitra-tour-kicker"><span>✦ MITRA’S LITTLE GUIDE · {index + 1}/{steps.length}</span><button onClick={close} aria-label="Close tour"><X size={17}/></button></div>
        <h2 id={`${id}-title`}>{rect ? current.title : 'Finding your next stop…'}</h2><p id={`${id}-body`}>{rect ? current.body : 'Waiting for this part of the page to be ready. You can skip the tour at any time.'}</p>
        <footer><button onClick={close}>Skip tour</button><div><button disabled={index === 0} onClick={() => setIndex(index - 1)}>Back</button><button className="mitra-tour-next" disabled={!rect} onClick={() => index + 1 < steps.length ? setIndex(index + 1) : close()}>{index + 1 === steps.length ? 'Done' : 'Next'}<span aria-hidden="true"> →</span></button></div></footer>
      </div>
    </div>, document.body)}
  </>;
}
