import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FarmWorkspace, Today } from "./FarmWorkspace";
const mocks = vi.hoisted(() => ({ fetch: vi.fn(), send: vi.fn() }));
vi.mock("@/lib/assistantClient", () => ({
  sendAssistant: mocks.send,
  useAssistant: () => ({ running: false, pending: null }),
}));
vi.mock("@/lib/apiClient", () => ({ apiFetch: mocks.fetch }));
vi.mock("@/components/VoiceInput", () => ({
  VoiceInput: ({ label }: { label: string }) => (
    <button type="button" aria-label={label}>
      Voice
    </button>
  ),
}));
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());
const reply = (data: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(data), { status }));
it("limits Today to three next steps and follows its named calendar destination", async () => {
  mocks.fetch.mockImplementation(() =>
    reply({
      actions: [1, 2, 3, 4].map((i) => ({
        id: String(i),
        title: `Step ${i}`,
        kind: "task",
        href: "calendar",
      })),
      provenance: { origin: "synthetic", lane: "demo" },
    }),
  );
  const navigate = vi.fn();
  render(<Today onNavigate={navigate} />);
  await screen.findByText("Step 1");
  expect(screen.queryByText("Step 4")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Step 1/ }));
  expect(navigate).toHaveBeenCalledWith("calendar");
  expect(screen.getAllByText("Sample").length).toBeGreaterThan(0);
});
it("saves actual rupee expenses using the exact server contract", async () => {
  mocks.fetch.mockImplementation((_p: string, o: RequestInit) =>
    reply(o.method === "POST" ? { id: "saved" } : { items: [] }),
  );
  render(<FarmWorkspace tab="ledger" onNavigate={vi.fn()} />);
  await screen.findByText(/Nothing saved/);
  fireEvent.click(screen.getByRole("button", { name: /Add entry/ }));
  fireEvent.change(screen.getByRole("textbox", { name: "What was it for?" }), {
    target: { value: "Seed payment" },
  });
  fireEvent.change(
    screen.getByRole("spinbutton", { name: "Amount in rupees" }),
    { target: { value: "1250" } },
  );
  fireEvent.change(screen.getByLabelText("Date"), {
    target: { value: "2026-10-14" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save record" }));
  await waitFor(() =>
    expect(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "POST"),
    ).toBeTruthy(),
  );
  expect(
    JSON.parse(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "POST")![1].body,
    ),
  ).toEqual({
    description: "Seed payment",
    amount_inr: 1250,
    kind: "expense",
    basis: "actual",
    category: "other",
    occurred_on: "2026-10-14",
    notes: "",
    cycle_id: null,
  });
});
it("preserves editor and explains stale version conflicts", async () => {
  mocks.fetch.mockImplementation((_p: string, o: RequestInit) =>
    o.method === "PATCH"
      ? reply({ detail: "This record changed. Refresh before editing." }, 409)
      : reply({
          items: [
            {
              id: "entry",
              description: "Seed",
              amount_inr: 50,
              basis: "actual",
              kind: "expense",
              category: "seed",
              occurred_on: "2026-10-14",
              row_version: 2,
            },
          ],
        }),
  );
  render(<FarmWorkspace tab="ledger" onNavigate={vi.fn()} />);
  await screen.findByText("Seed");
  fireEvent.click(screen.getByRole("button", { name: "Edit Seed" }));
  fireEvent.click(screen.getByRole("button", { name: "Save record" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Refresh before editing",
  );
  expect(screen.getByRole("dialog")).toBeInTheDocument();
});
it("corrects saved memory content through the dedicated endpoint", async () => {
  mocks.fetch.mockImplementation((_p: string, o: RequestInit) =>
    reply(
      o.method === "PATCH"
        ? {}
        : {
            items: [
              { id: "memory", fact_key: "crop", value: { content: "Wheat" } },
            ],
          },
    ),
  );
  render(<FarmWorkspace tab="memory" onNavigate={vi.fn()} />);
  await screen.findByText("Wheat");
  fireEvent.click(screen.getByRole("button", { name: "Edit saved fact" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Corrected fact" }), {
    target: { value: "Rice this season" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save record" }));
  await waitFor(() =>
    expect(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "PATCH"),
    ).toBeTruthy(),
  );
  expect(
    JSON.parse(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "PATCH")![1].body,
    ),
  ).toEqual({ value: "Rice this season" });
});
it("requires deletion review and sends the row version in the delete query", async () => {
  mocks.fetch.mockImplementation((_p: string, o: RequestInit) =>
    reply(
      o.method === "DELETE"
        ? {}
        : {
            items: [
              {
                id: "entry",
                description: "Seed",
                amount_inr: 50,
                row_version: 3,
              },
            ],
          },
    ),
  );
  render(<FarmWorkspace tab="ledger" onNavigate={vi.fn()} />);
  await screen.findByText("Seed");
  fireEvent.click(screen.getByRole("button", { name: "Review deleting Seed" }));
  expect(mocks.fetch.mock.calls.some(([, o]) => o.method === "DELETE")).toBe(
    false,
  );
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
  await waitFor(() =>
    expect(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "DELETE")?.[0],
    ).toContain("/entry?row_version=3"),
  );
});

it("starts an assistant run against the selected mission and keeps paused plans manual", async () => {
  mocks.fetch.mockImplementation(() =>
    reply({
      items: [
        {
          id: "plan",
          title: "Soil report",
          objective: "Prepare a dated soil summary",
          steps: [{ title: "Read saved report", done: false }],
          status: "active",
          row_version: 1,
        },
        {
          id: "paused",
          title: "Paused plan",
          objective: "",
          steps: [],
          status: "paused",
          row_version: 1,
        },
      ],
    }),
  );
  const navigate = vi.fn();
  render(<FarmWorkspace tab="missions" onNavigate={navigate} />);
  await screen.findByText("Soil report");
  const buttons = screen.getAllByRole("button", {
    name: /Work on this with Mitra/,
  });
  expect(buttons[1]).toBeDisabled();
  fireEvent.click(buttons[0]);
  expect(navigate).toHaveBeenCalledWith("chat");
  expect(mocks.send).toHaveBeenCalledWith(
    expect.stringContaining("Read saved report"),
    { mission_id: "plan", workspace_view: "records" },
  );
});
it("saves a crop season against an owned field using explicit sowing and harvest dates", async () => {
  mocks.fetch.mockImplementation((path: string, o: RequestInit) =>
    reply(
      o.method === "POST"
        ? { saved: true }
        : path.includes("/options")
          ? { regions: [], crops: [{ id: "crop", name: "Rice" }] }
          : path.endsWith("/plots")
            ? {
                plots: [
                  {
                    id: "plot",
                    farm_id: "farm",
                    plot_key: "North field",
                    area_ha: 1,
                    latitude: 30,
                    longitude: 75,
                  },
                ],
              }
            : path.endsWith("/farms")
              ? {
                  farms: [
                    {
                      id: "farm",
                      name: "Family farm",
                      ownership_type: "owned",
                      irrigation_method: "drip",
                    },
                  ],
                }
              : { crop_cycles: [] },
    ),
  );
  render(<FarmWorkspace tab="fields" onNavigate={vi.fn()} />);
  await screen.findByText("Family farm");
  fireEvent.click(screen.getByText("Crop seasons"));
  fireEvent.click(await screen.findByRole("button", { name: /Add season/ }));
  fireEvent.change(screen.getByRole("textbox", { name: "Season name" }), {
    target: { value: "Kharif 2026" },
  });
  fireEvent.change(screen.getByLabelText("Sowing date"), {
    target: { value: "2026-06-10" },
  });
  fireEvent.change(screen.getByLabelText("Expected harvest date"), {
    target: { value: "2026-10-30" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save season" }));
  await waitFor(() =>
    expect(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "POST"),
    ).toBeTruthy(),
  );
  expect(
    JSON.parse(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "POST")![1].body,
    ),
  ).toEqual({
    plot_id: "plot",
    crop_id: "crop",
    variety_id: null,
    season: "Kharif 2026",
    sowing_date: "2026-06-10",
    expected_harvest_date: "2026-10-30",
    actual_harvest_date: null,
    status: "planned",
  });
});
