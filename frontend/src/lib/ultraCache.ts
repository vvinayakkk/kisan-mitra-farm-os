import { reportedMarketsOnly } from "@/lib/localPresentation";
import { getAssistantSessionId, assistantAuthHeaders } from "./assistantClient";
import { apiFetch } from "@/lib/apiClient";
import { onWorkspaceCacheInvalidated } from "./workspaceCacheLifecycle";

const API_URL = import.meta.env.VITE_API_URL || "";
interface CacheEntry<T> { data: T; expiresAt: number }


export class UltraCacheEngine {
  private entries = new Map<string, CacheEntry<unknown>>();
  private inFlight = new Map<string, Promise<unknown>>();
  private epoch = 0;
  private defaultTTL = 60_000;
  constructor(private capacity = 48) {}
  clear(): void { this.epoch++; this.entries.clear(); this.inFlight.clear(); }
  private scoped(key: string): string | null {
    const owner = getAssistantSessionId();
    return owner ? `${owner}:${key}` : null;
  }
  set<T>(key: string, data: T, ttlMs = this.defaultTTL): void {
    const scoped = this.scoped(key);
    if (!scoped) return;
    this.entries.delete(scoped);
    this.entries.set(scoped, { data: structuredClone(data), expiresAt: Date.now() + ttlMs });
    while (this.entries.size > this.capacity) this.entries.delete(this.entries.keys().next().value!);
  }
  get<T>(key: string): T | null {
    const scoped = this.scoped(key);
    if (!scoped) return null;
    const entry = this.entries.get(scoped);
    if (!entry || entry.expiresAt <= Date.now()) { this.entries.delete(scoped); return null; }
    this.entries.delete(scoped); this.entries.set(scoped, entry);
    return structuredClone(entry.data) as T;
  }
  async fetchWithSWR<T>(key: string, fetcher: () => Promise<T>, ttlMs = this.defaultTTL,
    onBackgroundUpdate?: (fresh: T) => void, onBackgroundError?: (error: unknown) => void): Promise<T> {
    await assistantAuthHeaders();
    const owner = getAssistantSessionId(), epoch = this.epoch;
    const cached = this.get<T>(key), scoped = this.scoped(key)!;
    let pending = this.inFlight.get(scoped) as Promise<T> | undefined;
    if (!pending) {
      pending = Promise.resolve().then(fetcher).then(value => {
        if (owner !== getAssistantSessionId()) throw new Error("The farm session changed.");
        if (epoch === this.epoch) this.set(key, value, ttlMs);
        return value;
      }).finally(() => { if (this.inFlight.get(scoped) === pending) this.inFlight.delete(scoped); });
      this.inFlight.set(scoped, pending);
    }
    if (cached !== null) {

      void pending.then(value => {
        if (epoch === this.epoch && owner === getAssistantSessionId()) onBackgroundUpdate?.(structuredClone(value));
      }).catch(error => onBackgroundError?.(error));
      return cached;
    }
    return structuredClone(await pending);
  }
  private canWarm(): boolean {
    if (typeof document === "undefined" || document.visibilityState === "hidden" || !navigator.onLine) return false;
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
    return !connection?.saveData && !/(^|-)2g$/.test(connection?.effectiveType || "");
  }
  private async warmPaths(paths: string[]): Promise<void> {
    if (!this.canWarm()) return;
    await assistantAuthHeaders();
    const owner = getAssistantSessionId(), epoch = this.epoch;

    let cursor = 0;
    const worker = async () => {
      while (cursor < paths.length && epoch === this.epoch && owner === getAssistantSessionId() && this.canWarm()) {
        const path = paths[cursor++];
        try {

          const response = await apiFetch(`${API_URL}${path}`);
          if (!response.ok) continue;
        } catch {                                                                             }
      }
    };
    await Promise.all([worker(), worker()]);
  }
  warmUpPlatform(_phone?: string, stationId = "WS01"): void {
    void this.warmPaths([
      "/api/profile", "/api/farms", "/api/plots", "/api/farm-workspace/today",
      `/api/sensors/latest/${encodeURIComponent(stationId)}`,
      "/api/farm-workspace/weather-brief",
    ]).catch(() => {});
  }
  prewarmRoute(route: string): void {
    const paths: Record<string, string[]> = {
      "/mandi": [`/api/mandi?observed_only=${reportedMarketsOnly}&limit=100`],
      "/map": ["/api/marketplace/farmers"],
      "/trends": ["/api/sensors/trends/history?station_id=WS01&limit=50"],
      "/marketplace": ["/api/marketplace/farmers", "/api/marketplace/pooling"],
    };
    void this.warmPaths(paths[route] ?? []).catch(() => {});
  }
}
export const ultraCache = new UltraCacheEngine();
onWorkspaceCacheInvalidated(() => ultraCache.clear());
