import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import Admin from "./Admin";
const request = vi.hoisted(() => vi.fn());
vi.mock("@/lib/adminClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/adminClient")>()),
  adminRequest: request,
}));
vi.mock("@/lib/firebasePhoneAuth", () => ({
  watchPhoneIdentity: () => () => {},
  currentIdentityUid: () => null,
  sendPhoneCode: vi.fn(),
  confirmPhoneCode: vi.fn(),
  signOutPhone: vi.fn(),
}));
let role = "owner";
const farmer = {
  name: "farmers",
  label: "Farmers",
  group: "People",
  primary_key: ["id"],
  columns: [
    { name: "id", type: "UUID", primary_key: true },
    {
      name: "display_name",
      type: "TEXT",
      editable: true,
      references: [],
      nullable: false,
    },
  ],
};
afterEach(cleanup);
beforeEach(() => {
  role = "owner";
  request.mockReset();
  request.mockImplementation(async (path: string, body?: unknown) => {
    if (path === "/me") return { role, subject: "test" };
    if (path === "/overview")
      return {
        counts: { farmers: 1, farms: 2, tasks: 3, exchange_listings: 4 },
      };
    if (path === "/resources")
      return {
        resources: [
          {
            ...farmer,
            writable: role === "owner",
            deletable: role === "owner",
          },
        ],
      };
    if (path.includes("/preview"))
      return {
        id: "p",
        confirmation: "APPLY 1",
        notice: "Nothing saved",
        changes: [],
      };
    if (path.includes("/commit")) return { status: "applied" };
    return {
      records: [{ id: "f", display_name: "Asha", _version: "v" }],
      total: 1,
    };
  });
});
async function farmers() {
  await screen.findByText("Good things grow with care.");
  fireEvent.click(screen.getByText("People", { selector: "summary" }));
  fireEvent.click(screen.getByRole("button", { name: "Farmers" }));
  await screen.findByText("Asha");
}
describe("administration workspace", () => {
  it("does not reveal records to an unauthorized account", async () => {
    request.mockRejectedValue(
      new Error("This account does not have administrator access."),
    );
    render(<Admin />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "does not have administrator access",
    );
    expect(screen.queryByText("Asha")).toBeNull();
  });
  it("keeps a viewer read only", async () => {
    role = "viewer";
    render(<Admin />);
    await farmers();
    expect(screen.queryByRole("checkbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Open record 1" }));
    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Preview changes" }),
    ).toBeNull();
  });
  it("requires reason, preview and typed confirmation before sending a mutation", async () => {
    render(<Admin />);
    await farmers();
    fireEvent.click(screen.getByRole("button", { name: "Open record 1" }));
    fireEvent.change(screen.getByLabelText(/Display name/), {
      target: { value: "Asha Patil" },
    });
    expect(
      screen.getByRole("button", { name: "Preview changes" }),
    ).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for this change"), {
      target: { value: "Farmer requested name correction" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview changes" }));
    await screen.findByText("One last look.");
    expect(
      screen.getByRole("button", { name: "Apply reviewed changes" }),
    ).toBeDisabled();
    expect(request.mock.calls.some(([path]) => path.includes("/commit"))).toBe(
      false,
    );
    fireEvent.change(screen.getByLabelText(/Type APPLY 1/), {
      target: { value: "APPLY 1" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Apply reviewed changes" }),
    );
    await screen.findByText("Changes saved. The audit log has been updated.");
    expect(request).toHaveBeenCalledWith("/previews/p/commit", {
      confirmation: "APPLY 1",
    });
  });
});
