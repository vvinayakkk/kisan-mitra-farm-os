export type CacheInvalidationReason = "mutation" | "session" | "refresh";
const listeners = new Set<(reason: CacheInvalidationReason) => void>();
export function onWorkspaceCacheInvalidated(listener: (reason: CacheInvalidationReason) => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
export function invalidateWorkspaceCaches(reason: CacheInvalidationReason = "mutation"): void {
  listeners.forEach(listener => listener(reason));
}
