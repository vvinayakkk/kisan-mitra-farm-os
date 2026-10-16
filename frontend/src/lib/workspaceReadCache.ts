import { onWorkspaceCacheInvalidated } from "./workspaceCacheLifecycle";
/** Bounded, session-only cache for read tools. Never stores photos or mutations. */
export class WorkspaceReadCache {
  private entries = new Map<string, { value: unknown; expires: number }>();
  private pending = new Map<string, Promise<unknown>>();
  private epoch = 0;
  constructor(private capacity = 48, private ttl = 60_000) {}
  private key(scope: string, tool: string, args: Record<string, unknown>) {
    return JSON.stringify([scope, tool, Object.entries(args).sort(([a], [b]) => a.localeCompare(b))]);
  }
  peek<T>(scope: string, tool: string, args: Record<string, unknown>): T | null {
    const key = this.key(scope, tool, args), entry = this.entries.get(key);
    if (!entry || entry.expires <= Date.now()) { this.entries.delete(key); return null; }
    this.entries.delete(key); this.entries.set(key, entry);
    return structuredClone(entry.value) as T;
  }
  async read<T>(scope: string, tool: string, args: Record<string, unknown>, fetcher: () => Promise<T>): Promise<T> {
    const cached = this.peek<T>(scope, tool, args);
    if (cached !== null) return cached;
    const key = this.key(scope, tool, args), epoch = this.epoch;
    let promise = this.pending.get(key);
    if (!promise) {
      promise = fetcher().then(value => {
        if (epoch === this.epoch) {
          this.entries.set(key, { value: structuredClone(value), expires: Date.now() + this.ttl });
          while (this.entries.size > this.capacity) this.entries.delete(this.entries.keys().next().value!);
        }
        return value;
      }).finally(() => { if (this.pending.get(key) === promise) this.pending.delete(key); });
      this.pending.set(key, promise);
    }
    return structuredClone(await promise) as T;
  }
  clear() { this.epoch++; this.entries.clear(); this.pending.clear(); }
}
export const workspaceReadCache = new WorkspaceReadCache();
onWorkspaceCacheInvalidated(() => workspaceReadCache.clear());
