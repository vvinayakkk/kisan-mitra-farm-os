import { beforeEach, expect, it, vi } from "vitest";
import { cacheableRead, clearOfflineData, readSnapshot, saveSnapshot, setOfflineEnabled } from "./offlineStore";
beforeEach(() => { localStorage.clear(); vi.useRealTimers(); });
it("stores only opted-in snapshots and keeps farmer scopes separate", async () => {
  saveSnapshot("a", "/api/profile", JSON.stringify({ profile: { name: "A" } }));
  expect(readSnapshot("a", "/api/profile")).toBeNull();
  setOfflineEnabled(true); saveSnapshot("a", "/api/profile", JSON.stringify({ profile: { name: "A" } }));
  expect(readSnapshot("b", "/api/profile")).toBeNull();
  const snapshot = readSnapshot("a", "/api/profile")!;
  expect(snapshot.headers.get("X-Skyview-Offline")).toBe("true");
  expect((await snapshot.json()).offline_snapshot.writes_queued).toBe(false);
});
it("expires saved data and clears snapshots and drafts together", () => {
  vi.useFakeTimers(); setOfflineEnabled(true);
  saveSnapshot("a", "/api/profile", JSON.stringify({ profile: {} }));
  localStorage.setItem("skyview-draft-v1:a:chat", "Draft");
  vi.advanceTimersByTime(25 * 60 * 60 * 1000);
  expect(readSnapshot("a", "/api/profile")).toBeNull();
  clearOfflineData(); expect(localStorage.getItem("skyview-draft-v1:a:chat")).toBeNull();
});
it("never allows capability sessions, uploads, commands or memory into API snapshot allowlist", () => {
  for (const path of ["/api/assistant/sessions", "/api/voice/transcribe", "/api/devices", "/admin/tables", "/api/farm-workspace/memories"]) expect(cacheableRead(path)).toBe(false);
  expect(cacheableRead("/api/farm-workspace/today")).toBe(true);
});
it("marks retained provenance stale without changing source dates or demo labels", async () => {
  setOfflineEnabled(true);
  saveSnapshot("a", "/api/sensors/latest", JSON.stringify({ provenance: { origin: "synthetic", source: "Mock station", observed_at: "2026-10-10", stale: false }, chart: { provenance: { origin: "forecast", source: "Public weather", stale: false } } }));
  const data = await readSnapshot("a", "/api/sensors/latest")!.json();
  expect(data.provenance).toEqual({ origin: "synthetic", source: "Mock station", observed_at: "2026-10-10", stale: true });
  expect(data.chart.provenance.stale).toBe(true);
  expect(data.offline_snapshot.stale).toBe(true);
});
it("rejects cross-origin paths, forbidden API snapshots and empty owners", () => {
  setOfflineEnabled(true);
  expect(cacheableRead("https://untrusted.example/api/profile")).toBe(false);
  saveSnapshot("a", "/api/devices", "{}");
  saveSnapshot("", "/api/profile", "{}");
  saveSnapshot("a", "https://untrusted.example/api/profile", "{}");
  expect(readSnapshot("a", "/api/devices")).toBeNull();
  expect(readSnapshot("", "/api/profile")).toBeNull();
  expect(readSnapshot("a", "https://untrusted.example/api/profile")).toBeNull();
  expect(localStorage.length).toBe(1);
});
it("rejects corrupt and future-dated snapshot envelopes", () => {
  setOfflineEnabled(true);
  localStorage.setItem("skyview-offline-v1:a:/api/profile", "broken JSON");
  expect(readSnapshot("a", "/api/profile")).toBeNull();
  localStorage.setItem("skyview-offline-v1:a:/api/profile", JSON.stringify({ capturedAt: Date.now() + 60000, body: "{}" }));
  expect(readSnapshot("a", "/api/profile")).toBeNull();
  expect(localStorage.getItem("skyview-offline-v1:a:/api/profile")).toBeNull();
});
it("storage denial leaves the online application usable", () => {
  const get = vi.spyOn(localStorage, "getItem").mockImplementation(() => { throw new DOMException("Blocked", "SecurityError"); });
  expect(() => saveSnapshot("a", "/api/profile", "{}")).not.toThrow();
  expect(readSnapshot("a", "/api/profile")).toBeNull();
  get.mockRestore();
});
