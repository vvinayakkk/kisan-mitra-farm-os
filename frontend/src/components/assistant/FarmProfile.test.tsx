import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import FarmProfile from "./FarmProfile";
const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("@/lib/farmWorkspaceClient", () => ({
  workspaceRequest: mocks.request,
}));
vi.mock("@/components/VoiceInput", () => ({
  VoiceInput: ({ label }: { label: string }) => (
    <button type="button" aria-label={label}>
      Voice
    </button>
  ),
}));
afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());
const profile = {
  id: "farmer-1",
  name: "Real farmer",
  phone: "1234567890",
  district: "Kota",
  state: "Rajasthan",
  preferred_language: "hi",
  crops: ["Wheat"],
  provenance: { origin: "synthetic", lane: "demo" },
};
const setup = () =>
  mocks.request.mockImplementation((path: string) =>
    Promise.resolve(
      path === "/api/profile"
        ? { profile }
        : path === "/api/farms"
          ? { farms: [{ id: "farm-1", name: "My farm" }] }
          : {
              plots: [
                {
                  id: "plot-1",
                  farm_id: "farm-1",
                  name: "East field",
                  area_ha: 2,
                },
              ],
            },
    ),
  );
it("shows loaded identity and owned fields with an accessible notebook path", async () => {
  setup();
  const navigate = vi.fn();
  render(<FarmProfile onNavigate={navigate} />);
  await screen.findByText("Real farmer");
  expect(screen.getByText("East field")).toBeTruthy();
  expect(screen.getByText("1234567890")).toBeTruthy();
  expect(screen.getByText("हिन्दी")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Open farm notebook" }));
  expect(navigate).toHaveBeenCalledWith("records");
});
it("edits only supported fields without publishing or rewriting identity", async () => {
  setup();
  render(<FarmProfile onNavigate={vi.fn()} />);
  await screen.findByText("Real farmer");
  fireEvent.click(screen.getByRole("button", { name: "Edit details" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Your name" }), {
    target: { value: "Updated farmer" },
  });
  fireEvent.change(
    screen.getByRole("textbox", {
      name: "Resources you need (comma separated)",
    }),
    { target: { value: "Tractor, Transport" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
  await waitFor(() =>
    expect(mocks.request).toHaveBeenCalledWith(
      "/api/profile/save",
      "POST",
      expect.objectContaining({
        name: "Updated farmer",
        required_resources: ["Tractor", "Transport"],
      }),
    ),
  );
  const body = mocks.request.mock.calls.find(
    ([path]) => path === "/api/profile/save",
  )![2];
  expect(body.phone).toBeUndefined();
  expect(body.sharing_public).toBeUndefined();
});
it("keeps an unsuccessful edit available for retry", async () => {
  setup();
  render(<FarmProfile onNavigate={vi.fn()} />);
  await screen.findByText("Real farmer");
  fireEvent.click(screen.getByRole("button", { name: "Edit details" }));
  mocks.request.mockImplementation((path: string) =>
    path === "/api/profile/save"
      ? Promise.reject(new Error("Offline: changes not saved"))
      : Promise.resolve({ profile }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
  await screen.findByText("Offline: changes not saved");
  expect(screen.getByRole("textbox", { name: "Your name" })).toBeTruthy();
});
it("does not invent profile identity after a failed request", async () => {
  mocks.request.mockRejectedValue(new Error("Session unavailable"));
  render(<FarmProfile onNavigate={vi.fn()} />);
  await screen.findByText("Session unavailable");
  expect(screen.queryByText("Real farmer")).toBeNull();
  expect(screen.queryByRole("button", { name: "Edit details" })).toBeNull();
});
