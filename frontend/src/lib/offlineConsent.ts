export const OFFLINE_ENABLED_KEY = 'skyview-offline-enabled';
export function offlineEnabled(): boolean {
  try { return localStorage.getItem(OFFLINE_ENABLED_KEY) === 'true'; }
  catch { return false; }
}
