import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import { vi, test, expect, afterEach } from "vitest";
import WeatherWorkspace from "./WeatherWorkspace";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";

vi.mock("@/lib/farmWorkspaceClient", () => ({ workspaceRequest: vi.fn() }));
vi.mock("./MitraHelper", () => ({ MitraHelper: () => <button>Ask Mitra</button> }));

const forecast = {
  available: true,
  forecast: {
    farm: "North farm", farm_key: "north", records: [{ valid_on: "2026-10-16", temperature_max_c: 28, temperature_min_c: 19, rainfall_mm: 6 }],
    provenance: { source: "Open-Meteo", issued_at: "2026-10-15T19:00:00Z" }, note: "Regional model",
  },
  live: {
    current: { time: "2026-10-16T00:30", temperature_2m: 22, is_day: 0, weather_code: 61, precipitation: 2 },
    hourly: { time: ["2026-10-16T01:00"] },
    daily: { time: ["2026-10-16"], temperature_2m_max: [28], temperature_2m_min: [19], precipitation_sum: [6] },
    air: null, captured_at: "2026-10-15T19:00:00Z", source: "Open-Meteo", air_source: null,
  },
};

test("uses current rain and night data to render lightweight weather effects", async () => {
  vi.mocked(workspaceRequest).mockResolvedValue(forecast);
  const { container } = render(<WeatherWorkspace onNavigate={vi.fn()} />);
  await waitFor(() => expect(screen.getByRole("heading", { name: "Rain" })).toBeInTheDocument());
  expect(container.querySelector(".farm-weather-hero.weather-rain-night .weather-drops")?.children).toHaveLength(24);
  expect(screen.getByRole("button", { name: "Ask Mitra" })).toBeInTheDocument();
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test("nearby weather uses consented coarse device coordinates without saving a farm location", async () => {
  vi.mocked(workspaceRequest).mockClear();
  vi.mocked(workspaceRequest).mockResolvedValue(forecast);
  Object.defineProperty(navigator, "geolocation", {configurable:true, value:{getCurrentPosition:vi.fn(success => success({coords:{latitude:19.123456,longitude:73.987654}}))}});
  render(<WeatherWorkspace onNavigate={vi.fn()}/>);
  fireEvent.click(screen.getByRole("button",{name:"Use my location"}));
  await waitFor(() => expect(workspaceRequest).toHaveBeenCalledWith("/api/weather/location-dashboard?latitude=19.12&longitude=73.99", "GET", undefined, expect.any(Object)));
  expect(vi.mocked(workspaceRequest).mock.calls.every(([,method]) => !method || method === "GET")).toBe(true);
});
