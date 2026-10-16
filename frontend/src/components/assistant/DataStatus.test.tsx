import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataStatus, ProvenanceBadge, provenanceLabel } from "./DataStatus";
const api = vi.hoisted(() => vi.fn());
vi.mock("@/lib/apiClient", () => ({ apiFetch: api }));
afterEach(() => vi.clearAllMocks());
describe("source transparency", () => {
  it("separates demo, forecast and scenario and discloses stale measurements", () => {
    expect(provenanceLabel({ origin: "synthetic" })).toBe("Sample");
    expect(provenanceLabel({ origin: "scenario" })).toBe("Scenario");
    expect(provenanceLabel({ origin: "forecast" })).toBe("Forecast");
    render(<ProvenanceBadge value={{ origin: "observed", stale: true, source: "Station packet", observed_at: "2026-10-01" }} />);
    expect(screen.getByText("Observed · Older data")).toHaveAttribute("title", "Station packet · Dated 2026-10-01");
  });
  it("explains a demo database and exposes connector freshness without obscuring the workspace", async () => {
    api.mockResolvedValueOnce(Response.json({ mode: "demo", schema: "sv3", connectors: [{ name: "NASA POWER", status: "stale" }] }));
    render(<DataStatus />);
    await waitFor(() => expect(screen.getByText("Data sources")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Data sources"));
    expect(screen.getByText("NASA POWER")).toBeInTheDocument(); expect(screen.getByText("stale")).toBeInTheDocument();
  });
  it("shows loss of connection instead of silently calling data live", async () => {
    api.mockResolvedValueOnce(new Response("", { status: 503 })); render(<DataStatus />);
    await waitFor(() => expect(screen.getByText("Data connection unavailable")).toBeInTheDocument());
  });
});
