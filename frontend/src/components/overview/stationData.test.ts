import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchStation, reading } from "./stationData";
vi.mock("@/lib/assistantClient", () => ({ getAssistantSessionId: () => "session-1", assistantAuthHeaders: async () => ({ Authorization: "Bearer demo-token", "X-Assistant-Session": "session-1" }) }));
import { invalidateWorkspaceCaches } from "@/lib/workspaceCacheLifecycle";
beforeEach(() => invalidateWorkspaceCaches("session"));
afterEach(() => vi.unstubAllGlobals());
describe("station telemetry integrity", () => {
  it("rejects failed requests instead of substituting demo values", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Unavailable", { status: 503 })));
    await expect(fetchStation()).rejects.toThrow("Station unavailable");
  });
  it("preserves missing values and accepts snake case measurements", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({
          timestamp: "2026-10-13T10:00:00Z",
          wind_speed: 0,
          soil_moisture: 43,
      })),
    );
    const data = await fetchStation();
    expect(reading("anemometer", data)).toBe("0 km/h");
    expect(reading("soilSensor", data)).toBe("43%");
    expect(reading("rainGauge", data)).toBe("—");
    expect(data.batteryVoltage).toBeNull();
  });
  it("rejects packets without a valid measurement time", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ timestamp: "not-a-time", windSpeed: 12 })),
    );
    await expect(fetchStation()).rejects.toThrow("Invalid station timestamp");
  });
  it("does not turn string or non-finite values into valid measurements", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(
        '{"timestamp":"2026-10-13T10:00:00Z","rainfall":"2.5","temperature":1e999}',
        {headers: {"Content-Type": "application/json"}},
      )),
    );
    const data = await fetchStation();
    expect(data.rainfall).toBeNull();
    expect(data.temperature).toBeNull();
  });
  it("rejects the upstream mock fallback as live telemetry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({
          _source: "mock",
          timestamp: "2026-10-13T10:00:00Z",
          temperature: 25,
      })),
    );
    await expect(fetchStation()).rejects.toThrow("No measured station data");
  });
  it("accepts explicitly labelled demo packets without claiming they are real", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ data: { _source: "demo", timestamp: "2026-10-14T10:00:00Z", temperature: 25, provenance: { origin: "synthetic", lane: "demo" } } })));
    expect((await fetchStation()).provenance?.origin).toBe("synthetic");
  });
  it("interprets timezone-less backend timestamps as UTC", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({
          timestamp: "2026-10-13T10:00:00",
          temperature: 25,
      })),
    );
    expect((await fetchStation()).timestamp).toBe("2026-10-13T10:00:00Z");
  });
});
