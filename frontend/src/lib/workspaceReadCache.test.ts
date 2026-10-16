import { afterEach, expect, it, vi } from "vitest";
import { WorkspaceReadCache } from "./workspaceReadCache";
afterEach(() => vi.useRealTimers());
it("deduplicates reads, isolates owners, expires results and bounds retention", async () => {
  vi.useFakeTimers();
  const cache = new WorkspaceReadCache(2, 1000), fetcher = vi.fn(async () => ({ rows: [1] }));
  const [a, b] = await Promise.all([cache.read("A", "prices", { state: "X", crop: "Y" }, fetcher), cache.read("A", "prices", { crop: "Y", state: "X" }, fetcher)]);
  expect(fetcher).toHaveBeenCalledTimes(1);
  a.rows.push(2); expect(b.rows).toEqual([1]);
  expect(cache.peek("B", "prices", { crop: "Y", state: "X" })).toBeNull();
  vi.advanceTimersByTime(1001);
  expect(cache.peek("A", "prices", { crop: "Y", state: "X" })).toBeNull();
  await cache.read("A", "prices", { crop: "1" }, fetcher);
  await cache.read("A", "prices", { crop: "2" }, fetcher);
  await cache.read("A", "prices", { crop: "3" }, fetcher);
  expect(cache.peek("A", "prices", { crop: "1" })).toBeNull();
});
it("does not repopulate cleared cache from an old session's pending request", async () => {
  const cache = new WorkspaceReadCache();
  let finish!: (value: string) => void;
  const read = cache.read("old", "prices", {}, () => new Promise<string>(resolve => { finish = resolve; }));
  cache.clear(); finish("old data"); await read;
  expect(cache.peek("old", "prices", {})).toBeNull();
});
it("retries a failed read instead of caching failures", async () => {
  const cache = new WorkspaceReadCache(), fetcher = vi.fn().mockRejectedValueOnce(new Error("outage")).mockResolvedValue("fresh");
  await expect(cache.read("A", "prices", {}, fetcher)).rejects.toThrow("outage");
  await expect(cache.read("A", "prices", {}, fetcher)).resolves.toBe("fresh");
});
