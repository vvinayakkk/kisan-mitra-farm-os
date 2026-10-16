import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FarmResult } from "./FarmResult";
vi.mock("@/lib/assistantClient", () => ({
  downloadArtifact: vi.fn().mockResolvedValue(undefined),
}));
describe("generated file excerpts", () => {
  it("shows bounded sheet rows, full count and a download in the chat", () => {
    render(
      <FarmResult
        result={{
          artifact: {
            id: "sample",
            file_id: "sample",
            title: "Sample budget",
            format: "xlsx",
            filename: "sample.xlsx",
            size: 10,
            preview: {
              title: "Sample budget",
              sections: [],
              columns: ["Item", "Cost"],
              rows: [["Seed", 0]],
              row_count: 10,
              partial: true,
            },
          },
        }}
      />,
    );
    expect(screen.getByText("Seed")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("Showing 1 of 10 rows")).toBeInTheDocument();
    expect(screen.getByText("Preview · excerpt")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Preview · excerpt"));
    expect(
      screen.getByText("Preview · excerpt").closest("details"),
    ).not.toHaveAttribute("open");
  });
  it("renders document text safely without interpreting HTML", () => {
    const { container } = render(
      <FarmResult
        result={{
          artifact: {
            title: "Sample report",
            format: "docx",
            preview: {
              title: "Sample report",
              sections: [{ heading: "Notes", text: "<script>fake()</script>" }],
              columns: [],
              rows: [],
              row_count: 0,
              partial: false,
            },
          },
        }}
      />,
    );
    expect(screen.getByText("<script>fake()</script>")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
  });
});

it("labels weather forecasts with their own units and context", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  render(<FarmResult result={{ source: "Open-Meteo", provenance: { origin: "forecast" }, chart: { type: "line", kind: "weather_forecast", title: "Field rainfall outlook", unit: "mm", value_name: "Forecast rainfall", caption: "Issued grid-model weather forecast", points: [{ date: "2026-10-15", value: 0 }, { date: "2026-10-16", value: 2 }] } }} />);
  expect(screen.getByText("mm · Issued grid-model weather forecast")).toBeInTheDocument();
  expect(screen.getByText(/Model forecast, not station readings/)).toBeInTheDocument();
  expect(screen.queryByText("Price forecast")).toBeNull();
  vi.unstubAllGlobals();
});
