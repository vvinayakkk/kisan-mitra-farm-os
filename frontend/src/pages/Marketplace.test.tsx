import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import Marketplace from "./Marketplace";
import { MemoryRouter } from "react-router-dom";
import { apiFetch } from "@/lib/apiClient";
vi.mock("@/lib/apiClient", () => ({ apiFetch: vi.fn() }));
vi.mock("next-themes", () => ({ useTheme: () => ({ theme: "light" }) }));
vi.mock("@/hooks/use-toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({ language: "en" }),
}));
vi.mock("@/components/dashboard/DashboardHeader", () => ({
  DashboardHeader: () => null,
}));
vi.mock("@/components/AIOverview", () => ({ AIOverview: () => null }));
vi.mock("@/components/VoiceInput", () => ({ VoiceInput: () => null }));
vi.mock("@/components/FarmTheme", () => ({
  FarmBackground: () => null,
  GlassSection: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
const loop = {
  farmers: ["Loop farmer A", "Loop farmer B", "Loop farmer C"].map(
    (name, i) => ({
      id: `loop-${i}`,
      name,
      phone: null,
      whatsapp: null,
      location: "Punjab",
      crops: ["Wheat"],
      excess: ["Sprayer"],
      required: ["Harvest help"],
      exchange_listings: [{ id: `loop-listing-${i}`, kind: "offer" }],
    }),
  ),
  transfer_flow: [
    {
      from: "Loop farmer A",
      to: "Loop farmer B",
      item: "Sprayer",
      distance_km: 12,
    },
    {
      from: "Loop farmer B",
      to: "Loop farmer C",
      item: "Harvest help",
      distance_km: 13,
    },
    {
      from: "Loop farmer C",
      to: "Loop farmer A",
      item: "Transport",
      distance_km: 14,
    },
  ],
  total_distance_km: 39,
  ai_schedule: "Proposed only. Confirm timing and transport.",
};
const cluster = {
  region: "Punjab",
  farmer_count: 3,
  total_land_acres: 15,
  excess_pool: ["Sprayer"],
  required_pool: ["Harvest help"],
  optimization_plan: ["Discuss the shared resource first"],
  farmers: [{ name: "Pooling farmer", crops: null, phone: null }],
};
const matches = Array.from({ length: 40 }, (_, i) => ({
  id: `farmer-${i}`,
  name: `Directory farmer ${i}`,
  location: "Punjab",
  crops: ["Wheat"],
  phone: null,
  whatsapp_number: null,
  what_they_have: ["Sprayer"],
  what_they_need: ["Harvest help"],
  is_provider: true,
  match_type: "provider",
  distance_km: 12,
  exchange_listings: i === 0 ? [{ id: "listing-1", title: "Sprayer" }] : [],
}));
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem("user_name", "Wrong cached name");
  vi.mocked(apiFetch).mockImplementation(async (input) => {
    const url = String(input);
    const data = url.includes("/api/profile")
      ? {
          status: "success",
          profile: {
            id: "me",
            name: "Owned farmer",
            crops: ["Wheat"],
            excess_resources: ["Sprayer"],
            required_resources: ["Harvest help"],
          },
        }
      : url.includes("/match")
        ? { status: "success", matches }
        : url.includes("/pooling")
          ? { status: "success", clusters: [cluster] }
          : { status: "success", loops: [loop] };
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
});
it("renders forty private-contact farmers and links published resources to the actual exchange", async () => {
  render(
    <MemoryRouter>
      <Marketplace />
    </MemoryRouter>,
  );
  await screen.findByText("Directory farmer 39");
  expect(screen.getByText("Owned farmer")).toBeTruthy();
  expect(screen.queryByText("Wrong cached name")).toBeNull();
  expect(
    screen.getByRole("link", { name: "Discuss on SkyView" }),
  ).toHaveAttribute(
    "href",
    "/workspace?view=exchange&from=marketplace&listing=listing-1",
  );
  expect(
    screen
      .queryAllByRole("link")
      .some(
        (link) =>
          link.getAttribute("href")?.startsWith("tel:") ||
          link.getAttribute("href")?.startsWith("https://wa.me/"),
      ),
  ).toBe(false);
  expect(screen.getAllByText(/Contact details are private/)).toHaveLength(40);
});
it("opens the resource discussion modal safely when phone and WhatsApp remain private", async () => {
  render(
    <MemoryRouter>
      <Marketplace />
    </MemoryRouter>,
  );
  await screen.findByText("Directory farmer 39");
  fireEvent.click(
    screen.getAllByRole("button", { name: /Buy \/ Rent Tool/ })[0],
  );
  expect(
    screen.getAllByRole("link", { name: "Discuss on SkyView" }),
  ).toHaveLength(2);
  expect(screen.queryByRole("link", { name: /Call Provider/ })).toBeNull();
  expect(screen.getByText("Ask provider")).toBeTruthy();
});

it("renders circular barter and pooling with private contacts and nullable crops", async () => {
  render(
    <MemoryRouter>
      <Marketplace />
    </MemoryRouter>,
  );
  await screen.findByText("Directory farmer 39");
  fireEvent.click(
    screen.getByRole("button", { name: "Circular Barter (3-Party Loops)" }),
  );
  expect((await screen.findAllByText("Loop farmer C")).length).toBeGreaterThan(
    0,
  );
  expect(
    screen
      .queryAllByRole("link")
      .some((link) => link.getAttribute("href")?.startsWith("https://wa.me/")),
  ).toBe(false);
  fireEvent.click(
    screen.getByRole("button", { name: "Regional Pooling Optimization" }),
  );
  expect(await screen.findByText("Pooling farmer")).toBeTruthy();
});
