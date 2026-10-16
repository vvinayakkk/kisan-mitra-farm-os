import { clearAttachmentDrafts } from './attachmentDrafts';
import { offlineEnabled, OFFLINE_ENABLED_KEY as ENABLED } from './offlineConsent';
export { offlineEnabled } from './offlineConsent';

const PREFIX = "skyview-offline-v1:";
const TTL = 24 * 60 * 60 * 1000;
const ASSISTANT_SNAPSHOTS = new Set(["assistant-session", "assistant-catalog"]);
export function setOfflineEnabled(enabled: boolean): void {
  try {
    if (enabled) localStorage.setItem(ENABLED, "true");
    else { localStorage.removeItem(ENABLED); clearOfflineData(); }
  } catch {                                                                              }
  window.dispatchEvent(new Event("skyview-offline-change"));
}
export function clearOfflineData(): void {
  clearAttachmentDrafts();
  try {
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const key = localStorage.key(i);
      if (key?.startsWith(PREFIX) || key?.startsWith("skyview-draft-v1:")) localStorage.removeItem(key);
    }
  } catch {                                                                    }
}
function keyFor(session: string, url: string): string { return PREFIX + session + ":" + url; }
export function cacheableRead(url: string): boolean {
  try {
    const parsed = new URL(url, location.origin);
    const origins = [location.origin, import.meta.env.VITE_API_URL, import.meta.env.VITE_ASSISTANT_API_URL]
      .filter(Boolean).map(value => new URL(value as string, location.origin).origin);
    if (!origins.includes(parsed.origin) || parsed.username || parsed.password) return false;
    const path = parsed.pathname;
    return /^\/api\/(?:farms|plots|profile|data\/status|sensors\/(?:latest|health)|mandi(?:\/history)?|farm-workspace\/(?:today|ledger|cases|timeline))\/?$/.test(path)
      || /^\/api\/sensors\/latest\/[\w-]+$/.test(path);
  } catch { return false; }
}
function snapshotAllowed(session: string, url: string): boolean {
  return Boolean(session) && (ASSISTANT_SNAPSHOTS.has(url) || cacheableRead(url));
}
export function saveSnapshot(session: string, url: string, body: string): void {
  if (!offlineEnabled() || !snapshotAllowed(session, url) || body.length > 200000) return;
  try { localStorage.setItem(keyFor(session, url), JSON.stringify({ capturedAt: Date.now(), body })); }
  catch {                                                                         }
}

function markStale(value: unknown): void {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) { value.forEach(markStale); return; }
  const object = value as Record<string, unknown>;
  for (const [key, nested] of Object.entries(object)) {
    if (key === "provenance" && nested && typeof nested === "object" && !Array.isArray(nested)) {
      (nested as Record<string, unknown>).stale = true;
    }
    markStale(nested);
  }
}
export function readSnapshot(session: string, url: string): Response | null {
  if (!offlineEnabled() || !snapshotAllowed(session, url)) return null;
  try {
    const key = keyFor(session, url), raw = localStorage.getItem(key);
    if (!raw) return null;
    const value = JSON.parse(raw);
    const age = Date.now() - value.capturedAt;
    if (typeof value.body !== "string" || !Number.isFinite(value.capturedAt) || age < 0 || age > TTL) { localStorage.removeItem(key); return null; }
    const data = JSON.parse(value.body);
    if (!data || Array.isArray(data) || typeof data !== "object") return null;
    markStale(data);
    data.offline_snapshot = { captured_at: new Date(value.capturedAt).toISOString(), stale: true, writes_queued: false };
    return new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json", "X-Skyview-Offline": "true", "Cache-Control": "no-store" } });
  } catch { return null; }
}
