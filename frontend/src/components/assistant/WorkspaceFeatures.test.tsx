import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import WorkspaceFeatures from "./WorkspaceFeatures";
const mocks = vi.hoisted(() => ({ inspect: vi.fn(), upload: vi.fn(), request: vi.fn() }));
vi.mock("@/lib/farmWorkspaceClient", () => ({ workspaceRequest: mocks.request }));
vi.mock("@/lib/apiClient", () => ({ apiFetch: vi.fn(async () => ({ ok: true, json: async () => ({ commodities: ["Wheat", "Tomato"], states: ["Maharashtra", "Punjab"], markets: [{ id: "sample", name: "Sample mandi", state: "Maharashtra" }] }) })) }));
vi.mock("./PreparedBySaathi", () => ({ PreparedBySaathi: () => null }));
vi.mock("./AssistantChat", () => ({
  AssistantChat: ({ context }: { context: string }) => (
    <textarea aria-label={`${context} helper`} />
  ),
}));
vi.mock("@/lib/assistantClient", () => ({
  inspectWorkspaceTool: mocks.inspect,
  uploadAttachment: mocks.upload,
  useAssistant: () => ({
    ready: true,
    running: false,
    artifacts: [],
    tasks: [],
  }),
}));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
beforeEach(() => {
  vi.clearAllMocks();
  mocks.inspect.mockResolvedValue({ expenses: [] });
  mocks.request.mockResolvedValue({ row_version: 0, eligibility_reviewed: false, documents_reviewed: false, application_reviewed: false });
});
it("shows dated market observations while an unavailable trend stays unavailable", async () => {
  mocks.inspect.mockImplementation((tool: string) =>
    Promise.resolve(
      tool === "market_prices"
        ? {
            source: "Public test fixture",
            provenance: { origin: "synthetic", lane: "demo" },
            records: [
              {
                market: "Sample market",
                state: "Sample state",
                arrival_date: "2026-10-14",
                modal_price: 0,
                min_price: 0,
                max_price: 2,
              },
            ],
          }
        : { chart: null },
    ),
  );
  render(<WorkspaceFeatures view="markets" />);
  expect(await screen.findByText("Sample market")).toBeInTheDocument();
  expect(screen.getByText(/2026-10-14/)).toBeInTheDocument();
  expect(screen.getAllByText("Reference data").length).toBeGreaterThan(0);
  expect(screen.getByText(/enough dated observations/)).toBeInTheDocument();
  expect(mocks.inspect).toHaveBeenCalledWith("market_prices", {
    commodity: "Wheat",
    state: "",
    observed_only: false,
  });
});
it("shows data source failure instead of retaining invented prices", async () => {
  mocks.inspect.mockRejectedValue(new Error("Source unavailable"));
  render(<WorkspaceFeatures view="markets" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Source unavailable",
  );
  expect(screen.queryByText("Sample market")).not.toBeInTheDocument();
});
it("renders catalog provenance and refuses executable scheme links", async () => {
  mocks.inspect.mockResolvedValue({
    schemes: [
      {
        scheme_id: "sample",
        scheme_name: "Sample support",
        source: "fallback",
        eligibility: "Sample terms",
        official_url: "javascript:fake()",
      },
    ],
  });
  render(<WorkspaceFeatures view="schemes" />);
  expect(await screen.findByRole("heading", { name: "Sample support" })).toBeInTheDocument();
  expect(screen.getByText(/Reference catalog/)).toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: /Official information/ }),
  ).not.toBeInTheDocument();
});
it("searches an exact crop, state and mandi without showing future rates", async () => {
  mocks.inspect.mockImplementation((tool: string) => Promise.resolve(tool === "market_prices" ? { records: [{ market: "Available mandi", arrival_date: "2020-01-01", modal_price: 100 }, { market: "Future fixture", arrival_date: "2999-01-01", modal_price: 999 }] } : { chart: null }));
  render(<WorkspaceFeatures view="markets" />);
  expect(await screen.findByText("Available mandi")).toBeInTheDocument();
  expect(screen.queryByText("Future fixture")).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: "Crop" }), { target: { value: "Tomato" } });
  fireEvent.change(screen.getByRole("textbox", { name: "State optional" }), { target: { value: "Maharashtra" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Mandi optional" }), { target: { value: "Sample mandi" } });
  fireEvent.click(screen.getByRole("button", { name: "Find prices" }));
  await waitFor(() => expect(mocks.inspect).toHaveBeenCalledWith("market_trend", { commodity: "Tomato", state: "Maharashtra", market: "Sample mandi", observed_only: false }));
  expect(await screen.findByText("Available mandi")).toBeInTheDocument();
});
it("does not query hidden market and support pages", async () => {
  const view = render(<WorkspaceFeatures view="crops" />);
  expect(mocks.inspect).not.toHaveBeenCalled();
  view.rerender(<WorkspaceFeatures view="schemes" />);
  await waitFor(() => expect(mocks.inspect).toHaveBeenCalledWith("scheme_search", { query: "", state: "" }));
  expect(mocks.inspect).not.toHaveBeenCalledWith("market_prices", expect.anything());
});
it("does not show treatment when a crop photo has insufficient evidence", async () => {
  vi.stubGlobal("URL", {
    createObjectURL: () => "blob:sample",
    revokeObjectURL: vi.fn(),
  });
  mocks.upload.mockResolvedValue({ id: "sample" });
  mocks.inspect.mockResolvedValue({
    diagnostic: {
      disease_name: "Unknown",
      crop_identified: "Unknown",
      confidence: 0,
      description: "A real crop photo is needed.",
      symptoms: [],
      solutions: [
        {
          title: "Do not display",
          details: "Bad test advice",
          stage: "Immediate",
        },
      ],
    },
  });
  const { container } = render(<WorkspaceFeatures view="crops" />);
  await act(async () =>
    fireEvent.change(container.querySelector('input[type="file"]')!, {
      target: {
        files: [new File(["sample"], "sample.png", { type: "image/png" })],
      },
    }),
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Check this crop" }),
    ).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Check this crop" }));
  expect(
    await screen.findByText("A real crop photo is needed."),
  ).toBeInTheDocument();
  expect(screen.queryByText("Do not display")).not.toBeInTheDocument();
});
it.each([
  ["markets", "Crop", "Speak crop name", "Find prices"],
  [
    "schemes",
    "What do you need help with?",
    "Speak support search",
    "Explore support",
  ],
])(
  "keeps %s microphones inside their labelled inputs",
  async (view, label, mic, submit) => {
    const { container } = render(<WorkspaceFeatures view={view} />);
    const input = screen.getByRole("textbox", { name: label });
    expect(screen.getByRole("button", { name: mic }).parentElement).toBe(
      input.parentElement,
    );
    const state = screen.getByRole("textbox", { name: /State optional/ });
    expect(
      screen.getByRole("button", { name: "Speak state" }).parentElement,
    ).toBe(state.parentElement);
    const form = (await screen.findByRole("button", { name: submit })).closest("form")!;
    expect(form.children).toHaveLength(view === "markets" ? 4 : 3);
    expect(form.querySelectorAll(":scope > .voice-input-trigger")).toHaveLength(
      0,
    );
    expect(
      form.querySelector(".feature-search-field label")?.getAttribute("for"),
    ).toBe(input.id);
  },
);

it("compares returns only after explicit whole-trip costs and rejects unsupported price units", async () => {
  mocks.inspect.mockImplementation((tool: string) => Promise.resolve(tool === "market_prices" ? { records: [
    { market: "Pune", modal_price: 2500, unit: "INR/quintal", arrival_date: "2020-01-01" },
    { market: "Nashik", modal_price: 2600, unit: "INR/quintal", arrival_date: "2020-01-01" },
    { market: "Per kg market", modal_price: 25, unit: "INR/kg", arrival_date: "2020-01-01" },
  ] } : { chart: null }));
  render(<WorkspaceFeatures view="markets" />);
  const choices = await screen.findAllByRole("button", { name: "Compare take-home" });
  expect(choices[2]).toBeDisabled();
  fireEvent.click(choices[0]); fireEvent.click(choices[1]);
  const compare = screen.getByRole("region", { name: "Compare take-home amount" });
  expect(within(compare).getAllByText("Add your costs")).toHaveLength(2);
  expect(within(compare).queryByText("Highest estimated return")).not.toBeInTheDocument();
  for (const [name, value] of [["Pune transport", "500"], ["Pune fees", "100"], ["Nashik transport", "2000"], ["Nashik fees", "0"]]) {
    fireEvent.change(screen.getByRole("spinbutton", { name }), { target: { value } });
  }
  expect(within(compare).getByText("₹24,400")).toBeInTheDocument();
  expect(within(compare).getByText("₹24,000")).toBeInTheDocument();
  expect(within(compare).getByText("Highest estimated return").closest("article")).toHaveTextContent("Pune");
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity to sell in quintals" }), { target: { value: "0" } });
  expect(within(compare).getByRole("alert")).toHaveTextContent("greater than zero");
  expect(within(compare).queryByText("Highest estimated return")).not.toBeInTheDocument();
});

it("keeps scheme readiness separate and prepares a contextual chat draft", async () => {
  mocks.inspect.mockResolvedValue({ schemes: [
    { id: "00000000-0000-0000-0000-000000000001", name: "Water support", state: "Punjab", eligibility: "Water terms", official_url: "https://example.gov.in/water" },
    { id: "00000000-0000-0000-0000-000000000002", name: "Soil support", eligibility: "Soil terms" },
  ] });
  const persisted: Record<string, Record<string, unknown>> = {};
  mocks.request.mockImplementation(async (path: string, method = "GET", body?: Record<string, unknown>) => {
    if (method === "PUT") persisted[path] = { ...body, row_version: Number(body?.row_version) + 1 };
    return persisted[path] || { row_version: 0, eligibility_reviewed: false, documents_reviewed: false, application_reviewed: false };
  });
  const navigate = vi.fn(), draft = vi.fn();
  window.addEventListener("mitra-voice-draft", draft);
  render(<WorkspaceFeatures view="schemes" onNavigate={navigate} />);
  await screen.findByRole("heading", { name: "Water support" });
  await waitFor(() => expect(screen.getByRole("checkbox", { name: "I have checked who can apply" })).toBeEnabled());
  fireEvent.click(screen.getByRole("checkbox", { name: "I have checked who can apply" }));
  await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("/api/support-folder/00000000-0000-0000-0000-000000000001", "PUT", { row_version: 0, eligibility_reviewed: true, documents_reviewed: false, application_reviewed: false }));
  fireEvent.click(screen.getByRole("button", { name: /Soil support/ }));
  expect(screen.getByRole("checkbox", { name: "I have checked who can apply" })).not.toBeChecked();
  expect(screen.getByText("Soil terms")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Water support/ }));
  await waitFor(() => expect(screen.getByRole("checkbox", { name: "I have checked who can apply" })).toBeChecked());
  expect(screen.getByRole("link", { name: "Official information" })).toHaveAttribute("href", "https://example.gov.in/water");
  fireEvent.click(screen.getByRole("button", { name: "Prepare with Mitra" }));
  expect(navigate).toHaveBeenCalledWith("chat");
  expect(draft.mock.calls[0][0].detail).toContain("Water support in Punjab");
  expect(draft.mock.calls[0][0].detail).toContain("https://example.gov.in/water");
  window.removeEventListener("mitra-voice-draft", draft);
});

it("rolls back a conflicted checklist write and offers a fresh reload", async () => {
  mocks.inspect.mockResolvedValue({ schemes: [{ id: "00000000-0000-0000-0000-000000000003", name: "Support" }] });
  mocks.request.mockImplementation(async (_path, method = "GET") => {
    if (method === "PUT") throw new Error("This checklist changed elsewhere.");
    return { row_version: 2, eligibility_reviewed: false, documents_reviewed: false, application_reviewed: false };
  });
  render(<WorkspaceFeatures view="schemes" />);
  const checkbox = await screen.findByRole("checkbox", { name: "I have checked who can apply" });
  await waitFor(() => expect(checkbox).toBeEnabled());
  fireEvent.click(checkbox);
  expect(await screen.findByRole("alert")).toHaveTextContent("changed elsewhere");
  expect(checkbox).not.toBeChecked();
  expect(checkbox).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Reload checklist" }));
  await waitFor(() => expect(checkbox).toBeEnabled());
});
