import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SharedFarmWork } from "./SharedFarmWork";
const mocks = vi.hoisted(() => ({ fetch: vi.fn() }));
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
it("does not load secondary notebooks until the farmer expands them", async () => {
  render(<SharedFarmWork />);
  expect(mocks.fetch).not.toHaveBeenCalled();
});
it("records a service quote without claiming to book the supplier", async () => {
  mocks.fetch.mockImplementation((_p: string, o: RequestInit) =>
    reply(o.method === "POST" ? { id: "service" } : { items: [] }),
  );
  render(<SharedFarmWork />);
  fireEvent.click(screen.getByText("Your service notebook"));
  fireEvent.click(
    await screen.findByRole("button", { name: /Add arrangement/ }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Arrangement title" }), {
    target: { value: "Harvest tractor" },
  });
  fireEvent.change(
    screen.getByRole("spinbutton", { name: "Quote in rupees" }),
    { target: { value: "2500" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Save arrangement" }));
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
    title: "Harvest tractor",
    service_type: "other",
    supplier: "",
    quote_inr: 2500,
    scheduled_on: null,
    notes: "",
    status: "planned",
  });
});
it("requires a sharing review before joining a group with its code", async () => {
  mocks.fetch.mockImplementation((_p: string, o: RequestInit) =>
    reply(
      o.method === "POST"
        ? { id: "group", name: "Family", role: "reader" }
        : { items: [] },
    ),
  );
  render(<SharedFarmWork />);
  fireEvent.click(screen.getByText("Family & FPO plans"));
  fireEvent.click(
    await screen.findByRole("button", { name: "Join with a code" }),
  );
  fireEvent.change(screen.getByRole("textbox", { name: "Invitation code" }), {
    target: { value: "invite-code" },
  });
  expect(
    screen.getByRole("button", { name: "Join this group" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(screen.getByRole("button", { name: "Join this group" }));
  await waitFor(() =>
    expect(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "POST"),
    ).toBeTruthy(),
  );
  expect(
    mocks.fetch.mock.calls.find(([, o]) => o.method === "POST")![0],
  ).toContain("/groups/join");
  expect(
    JSON.parse(
      mocks.fetch.mock.calls.find(([, o]) => o.method === "POST")![1].body,
    ),
  ).toEqual({ code: "invite-code", consent_to_share_display_name: true });
});
it("keeps reader group plans read only", async () => {
  mocks.fetch.mockImplementation((p: string) =>
    reply(
      p.endsWith("/tasks")
        ? {
            items: [
              {
                id: "task",
                title: "Field inspection",
                completed: false,
                row_version: 1,
              },
            ],
          }
        : { items: [{ id: "group", name: "Family", role: "reader" }] },
    ),
  );
  render(<SharedFarmWork />);
  fireEvent.click(screen.getByText("Family & FPO plans"));
  expect(
    await screen.findByRole("checkbox", { name: "Complete Field inspection" }),
  ).toBeDisabled();
  expect(screen.queryByRole("button", { name: /Invite someone/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /Add shared task/ })).toBeNull();
});
it("requires owner consent before generating a one-use invite and never copies automatically", async () => {
  mocks.fetch.mockImplementation((p: string, o: RequestInit) =>
    reply(
      o.method === "POST"
        ? { code: "once-only-code", expires_at: "2026-10-21T00:00:00Z" }
        : p.endsWith("/groups")
          ? { items: [{ id: "group", name: "Family", role: "owner" }] }
          : { items: [] },
    ),
  );
  render(<SharedFarmWork />);
  fireEvent.click(screen.getByText("Family & FPO plans"));
  fireEvent.click(
    await screen.findByRole("button", { name: "Invite someone" }),
  );
  expect(
    screen.getByRole("button", { name: "Create invitation code" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(
    screen.getByRole("button", { name: "Create invitation code" }),
  );
  expect(await screen.findByText("once-only-code")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Copy code" })).toBeInTheDocument();
});
