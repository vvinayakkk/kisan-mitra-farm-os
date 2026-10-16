import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FarmExchange from "./FarmExchange";
import { exchangeRequest, exchangeWrite } from "@/lib/exchangeClient";
vi.mock("@/lib/exchangeClient", () => ({
  exchangeRequest: vi.fn(),
  exchangeWrite: vi.fn(),
}));
vi.mock("@/components/WorkspaceVoiceField", () => ({
  WorkspaceVoiceField: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
const listing = {
  id: "l1",
  title: "Shared sprayer",
  category: "equipment",
  kind: "offer",
  description: "Good condition",
  quantity: 1,
  unit: "day",
  state: "Punjab",
  district: "Ludhiana",
  exchange_for: "Help with harvest",
  status: "published",
  row_version: 1,
};
describe("Farmer exchange", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(exchangeRequest).mockImplementation(async (path) => ({
      items: path.includes("/listings") ? [listing] : [],
    }));
  });
  it("opens a linked notice for review without creating a conversation and can return to all resources", async () => {
    render(<FarmExchange initialListingId="l1" />);
    await screen.findByText("Shared sprayer");
    expect(vi.mocked(exchangeRequest).mock.calls.some(([path]) => path.includes("listing_id=l1"))).toBe(true);
    expect(exchangeWrite).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Show all resources" }));
    await waitFor(() => expect(vi.mocked(exchangeRequest).mock.calls.filter(([path]) => path.startsWith("/listings?")).slice(-1)[0]?.[0]).not.toContain("listing_id"));
  });
  it("discloses requester identity before opening actual conversation", async () => {
    vi.mocked(exchangeWrite).mockResolvedValue({ id: "c1" });
    render(<FarmExchange />);
    await screen.findByText("Shared sprayer");
    expect(
      screen.getByText("Connecting shares your name with this member."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Discuss exchange/ }));
    await waitFor(() =>
      expect(exchangeWrite).toHaveBeenCalledWith("/conversations", {
        listing_id: "l1",
        consent_to_share_display_name: true,
      }),
    );
  });
  it("requires explicit consent to publish a member resource", async () => {
    render(<FarmExchange />);
    fireEvent.click(
      screen.getByRole("button", { name: "Post an offer or need" }),
    );
    expect(
      screen.getByRole("button", { name: "Publish resource" }),
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(
      screen.getByRole("button", { name: "Publish resource" }),
    ).toBeEnabled();
  });
  it("exposes own listing management and actual matching endpoint", async () => {
    render(<FarmExchange />);
    await screen.findByText("Shared sprayer");
    fireEvent.click(
      screen.getByRole("button", { name: "Manage my resources" }),
    );
    await screen.findByRole("button", { name: "Find suitable matches" });
    fireEvent.click(
      screen.getByRole("button", { name: "Find suitable matches" }),
    );
    await waitFor(() =>
      expect(exchangeRequest).toHaveBeenCalledWith(
        "/matches?listing_id=l1",
        expect.anything(),
      ),
    );
  });
  it("moves Mitra's draft into editable fields without publishing", async () => {
    vi.mocked(exchangeRequest).mockImplementation(async (path) =>
      path === "/assist"
        ? {
            answer: "Review the resource first",
            saved: false,
            draft: {
              kind: "listing",
              fields: {
                title: "Sprayer available",
                quantity: 2,
                unit: "day",
                state: "Punjab",
                district: "Ludhiana",
                description: "Good condition",
                category: "equipment",
                kind: "offer",
              },
            },
          }
        : { items: path.includes("/listings") ? [listing] : [] },
    );
    render(<FarmExchange />);
    fireEvent.change(
      screen.getByRole("textbox", { name: "Ask exchange Mitra" }),
      { target: { value: "I have a sprayer for two days" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Ask Mitra" }));
    fireEvent.click(
      await screen.findByRole("button", { name: /Review this draft/ }),
    );
    expect(screen.getByRole("textbox", { name: "Resource title" })).toHaveValue(
      "Sprayer available",
    );
    expect(screen.getByRole("spinbutton", { name: "Quantity" })).toHaveValue(2);
    expect(
      screen.getByRole("button", { name: "Publish resource" }),
    ).toBeDisabled();
    expect(exchangeWrite).not.toHaveBeenCalled();
  });
});
