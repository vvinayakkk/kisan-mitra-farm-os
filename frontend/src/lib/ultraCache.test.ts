import { afterEach, expect, it, vi } from "vitest";
const identity = vi.hoisted(() => ({ owner: "farm-a" }));
vi.mock("./assistantClient", () => ({ getAssistantSessionId: () => identity.owner, assistantAuthHeaders: vi.fn(async () => ({})) }));
vi.mock("./apiClient", () => ({ apiFetch: vi.fn() }));
import { UltraCacheEngine } from "./ultraCache";
afterEach(() => { vi.useRealTimers(); identity.owner = "farm-a"; });
it("expires and bounds snapshots and isolates owners and caller mutations", () => {
  vi.useFakeTimers();
  const cache = new UltraCacheEngine(2);
  cache.set("a", { count: 1 }, 1000);
  cache.get<{ count: number }>("a")!.count = 9;
  expect(cache.get("a")).toEqual({ count: 1 });
  identity.owner = "farm-b"; expect(cache.get("a")).toBeNull(); identity.owner = "farm-a";
  vi.advanceTimersByTime(1001); expect(cache.get("a")).toBeNull();
  cache.set("a", 1); cache.set("b", 2); cache.set("c", 3);
  expect(cache.get("a")).toBeNull();
});
it("notifies every coalesced background subscriber", async () => {
  const cache = new UltraCacheEngine(); cache.set("prices", "old");
  let finish!: (value: string) => void;
  const fetcher = vi.fn(() => new Promise<string>(resolve => { finish = resolve; }));
  const first = vi.fn(), second = vi.fn();
  expect(await Promise.all([cache.fetchWithSWR("prices", fetcher, 1000, first), cache.fetchWithSWR("prices", fetcher, 1000, second)])).toEqual(["old", "old"]);
  expect(fetcher).toHaveBeenCalledTimes(1);
  finish("fresh"); await vi.waitFor(() => expect(second).toHaveBeenCalledWith("fresh"));
  expect(first).toHaveBeenCalledWith("fresh");
});
it("does not notify subscribers or restore snapshots after invalidation", async () => {
  const cache = new UltraCacheEngine(); cache.set("prices", "old");
  let finish!: (value: string) => void;
  const update = vi.fn();
  await cache.fetchWithSWR("prices", () => new Promise<string>(resolve => { finish = resolve; }), 1000, update);
  cache.clear(); finish("stale"); await new Promise(resolve => setTimeout(resolve, 0));
  expect(update).not.toHaveBeenCalled(); expect(cache.get("prices")).toBeNull();
});
it("surfaces background failure to each subscriber", async () => {
  const cache = new UltraCacheEngine(); cache.set("prices", "old");
  const failed = vi.fn();
  await cache.fetchWithSWR("prices", async () => { throw new Error("outage"); }, 1000, undefined, failed);
  await vi.waitFor(() => expect(failed).toHaveBeenCalledWith(expect.objectContaining({ message: "outage" })));
});
