import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const auth = vi.hoisted(() => vi.fn());
const current = vi.hoisted(() => ({ session: "server-session" }));
vi.mock("./assistantClient", () => ({ getAssistantSessionId: () => current.session, assistantAuthHeaders: auth }));
import { apiFetch } from "./apiClient";
import { readSnapshot, saveSnapshot, setOfflineEnabled } from "./offlineStore";
beforeEach(() => { current.session = "server-session"; localStorage.clear(); auth.mockResolvedValue({ Authorization: "Bearer issued-capability", "X-Assistant-Session": "server-session" }); });
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
describe("farmer capability API", () => {
  it("overwrites caller identity headers while retaining content type and abort signal", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}")); vi.stubGlobal("fetch", fetch);
    const signal = new AbortController().signal;
    await apiFetch("/api/profile", { method: "POST", body: "{}", signal, headers: { Authorization: "Bearer wrong", "X-Assistant-Session": "other-farmer", "Content-Type": "application/json" } });
    const options = fetch.mock.calls[0][1] as RequestInit;
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer issued-capability");
    expect(new Headers(options.headers).get("X-Assistant-Session")).toBe("server-session");
    expect(new Headers(options.headers).get("Content-Type")).toBe("application/json"); expect(options.signal).toBe(signal);
  });
  it("does not send unauthenticated farmer requests when the session cannot initialize", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch); auth.mockRejectedValueOnce(new Error("Session unavailable"));
    await expect(apiFetch("/api/profile")).rejects.toThrow("Session unavailable"); expect(fetch).not.toHaveBeenCalled();
  });
  it("does not dispatch a cancelled request after authentication", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch); const controller = new AbortController(); controller.abort();
    await expect(apiFetch("/api/profile", { signal: controller.signal })).rejects.toThrow("Request cancelled"); expect(fetch).not.toHaveBeenCalled();
  });
});

describe("owner-scoped offline reads", () => {
  it("falls back only to explicitly saved reads for the current owner", async () => {
    setOfflineEnabled(true);
    saveSnapshot("server-session", "/api/profile", JSON.stringify({ profile: { name: "A" }, provenance: { origin: "synthetic", stale: false } }));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Network unreachable")));
    const response = await apiFetch("/api/profile");
    expect(response.headers.get("X-Skyview-Offline")).toBe("true");
    const body = await response.json();
    expect(body.profile.name).toBe("A");
    expect(body.provenance.stale).toBe(true);
    expect(body.offline_snapshot.writes_queued).toBe(false);
  });
  it("never uses offline snapshots to disguise denied sessions or failed writes", async () => {
    setOfflineEnabled(true); saveSnapshot("server-session", "/api/profile", "{}");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Denied", { status: 401 })));
    expect((await apiFetch("/api/profile")).status).toBe(401);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Offline")));
    await expect(apiFetch("/api/profile", { method: "PUT", body: "{}" })).rejects.toThrow("Offline");
  });
  it("rejects identity changes during authentication before dispatching", async () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    auth.mockImplementationOnce(async () => { current.session = "new-session"; return { Authorization: "Bearer old-token", "X-Assistant-Session": "server-session" }; });
    await expect(apiFetch("/api/profile")).rejects.toThrow("session changed");
    expect(fetch).not.toHaveBeenCalled();
  });
  it("ignores successful responses from a farm that was logged out while fetching", async () => {
    setOfflineEnabled(true);
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => { current.session = "new-session"; return new Response(JSON.stringify({ profile: { name: "Old owner" } })); }));
    await expect(apiFetch("/api/profile")).rejects.toThrow("session changed");
    expect(readSnapshot("new-session", "/api/profile")).toBeNull();
    expect(readSnapshot("server-session", "/api/profile")).toBeNull();
  });
  it("does not return another owner's snapshot when offline", async () => {
    setOfflineEnabled(true); saveSnapshot("old-session", "/api/profile", JSON.stringify({ profile: { name: "Old owner" } }));
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Offline")));
    await expect(apiFetch("/api/profile")).rejects.toThrow("Offline");
  });
  it("does not fall back after the farmer cancels the request", async () => {
    setOfflineEnabled(true); saveSnapshot("server-session", "/api/profile", "{}");
    const abort = new AbortController();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => { abort.abort(); throw new TypeError("Offline"); }));
    await expect(apiFetch("/api/profile", { signal: abort.signal })).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("warm read cache", () => {
  it("shares a signaled read while cancelling only the consumer that aborts", async () => {
    const { invalidateWorkspaceCaches } = await import("./workspaceCacheLifecycle");
    invalidateWorkspaceCaches("session");
    let finish!: (value: Response) => void;
    const fetch = vi.fn(() => new Promise<Response>(resolve => {finish=resolve;}));
    vi.stubGlobal("fetch", fetch);
    const firstController = new AbortController(), secondController = new AbortController();
    const first = apiFetch("/api/farm-workspace/expenses", {signal: firstController.signal});
    const second = apiFetch("/api/farm-workspace/expenses", {signal: secondController.signal});
    const rejected = expect(first).rejects.toMatchObject({name: "AbortError"});
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const requestSignal = (fetch.mock.calls[0] as unknown as [string, RequestInit])[1].signal!;
    expect(requestSignal).not.toBe(firstController.signal);
    firstController.abort(); await rejected; expect(requestSignal.aborted).toBe(false);
    const third = apiFetch("/api/farm-workspace/expenses", {signal: new AbortController().signal});
    finish(Response.json({expenses: [{id: "expense-1"}]}));
    expect(await (await second).json()).toEqual({expenses: [{id: "expense-1"}]});
    expect(await (await third).json()).toEqual({expenses: [{id: "expense-1"}]});
    const cached = await apiFetch("/api/farm-workspace/expenses", {signal: new AbortController().signal});
    expect(await cached.json()).toEqual({expenses: [{id: "expense-1"}]});
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("uses a warmed response for a subsequent signaled page read", async () => {
    const { invalidateWorkspaceCaches } = await import("./workspaceCacheLifecycle");
    invalidateWorkspaceCaches("session");
    const fetch = vi.fn(async () => Response.json({plots: []})); vi.stubGlobal("fetch", fetch);
    await apiFetch("/api/plots");
    const controller = new AbortController();
    expect(await (await apiFetch("/api/plots", {signal: controller.signal})).json()).toEqual({plots: []});
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("returns uncached media directly without leaving an unread cloned stream", async () => {
    const response = new Response("audio bytes", {headers: {"Content-Type": "audio/mpeg"}});
    const clone = vi.spyOn(response, "clone");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    expect(await apiFetch("/api/assistant/audio/response.mp3")).toBe(response);
    expect(clone).not.toHaveBeenCalled();
  });
  it("coalesces reads and invalidates after successful writes", async () => {
    const { invalidateWorkspaceCaches } = await import("./workspaceCacheLifecycle");
    invalidateWorkspaceCaches("session");
    const fetch = vi.fn(async () => Response.json({ revision: 1 })); vi.stubGlobal("fetch", fetch);
    const [first, second] = await Promise.all([apiFetch("/api/plots"), apiFetch("/api/plots")]);
    expect(await first.json()).toEqual({ revision: 1 }); expect(await second.json()).toEqual({ revision: 1 });
    expect(fetch).toHaveBeenCalledTimes(1);
    await apiFetch("/api/plots"); expect(fetch).toHaveBeenCalledTimes(1);
    await apiFetch("/api/plots", { method: "POST", body: "{}" });
    await apiFetch("/api/plots"); expect(fetch).toHaveBeenCalledTimes(3);
  });
  it("honors fresh reads and expires cached responses", async () => {
    const { invalidateWorkspaceCaches } = await import("./workspaceCacheLifecycle");
    invalidateWorkspaceCaches("session");
    const fetch = vi.fn(async () => Response.json({ rows: [] })); vi.stubGlobal("fetch", fetch);
    await apiFetch("/api/farms"); await apiFetch("/api/farms", { cache: "no-store" });
    expect(fetch).toHaveBeenCalledTimes(2);
    const clock = vi.spyOn(Date, "now").mockReturnValue(Date.now() + 16000);
    await apiFetch("/api/farms"); expect(fetch).toHaveBeenCalledTimes(3); clock.mockRestore();
  });
  it("aborts background reads when the session clears", async () => {
    const { invalidateWorkspaceCaches } = await import("./workspaceCacheLifecycle");
    invalidateWorkspaceCaches("session");
    let started!: () => void;
    const dispatched = new Promise<void>(resolve => { started = resolve; });
    vi.stubGlobal("fetch", vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")));
      started();
    })));
    const request = apiFetch("/api/plots"); await dispatched;
    invalidateWorkspaceCaches("session");
    await expect(request).rejects.toThrow("Cancelled");
  });
  it("does not retain a pre-mutation in-flight read", async () => {
    const { invalidateWorkspaceCaches } = await import("./workspaceCacheLifecycle");
    invalidateWorkspaceCaches("session");
    let finish!: (response: Response) => void;
    const fetch = vi.fn().mockImplementationOnce(() => new Promise<Response>(resolve => { finish = resolve; })).mockImplementation(async () => Response.json({ revision: 2 }));
    vi.stubGlobal("fetch", fetch);
    const old = apiFetch("/api/plots"); await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    invalidateWorkspaceCaches("mutation"); finish(Response.json({ revision: 1 })); await old;
    expect(await (await apiFetch("/api/plots")).json()).toEqual({ revision: 2 });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
