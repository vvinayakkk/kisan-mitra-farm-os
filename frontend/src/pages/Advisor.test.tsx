import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Advisor from "./Advisor";
vi.mock("@/components/assistant/FarmSetup", () => ({ FarmSetup: () => null }));
vi.mock("@/contexts/LanguageContext", () => ({
  useLanguage: () => ({ language: "en", setLanguage: vi.fn() }),
}));
vi.mock("@/components/assistant/AssistantChat", () => ({
  AssistantChat: () => null,
}));
vi.mock("@/components/assistant/FarmCalendar", () => ({
  FarmCalendar: () => null,
}));
vi.mock("@/components/assistant/WeatherShortcut", () => ({
  WeatherShortcut: () => null,
}));
vi.mock("./SystemOverview", () => ({ default: () => null }));
vi.mock("@/components/assistant/WorkspaceFeatures", () => ({
  default: () => null,
}));
afterEach(cleanup);
it("keeps one station control, every page icon and the original return destination", async () => {
  await act(async () => {
    render(
      <MemoryRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        initialEntries={["/workspace?view=station&from=overview"]}
      >
        <Advisor />
      </MemoryRouter>,
    );
  });
  expect(screen.getAllByRole("button", { name: "Farm station" })).toHaveLength(
    1,
  );
  const navigation = screen.getByRole("navigation", {
    name: "Farm tools",
  });
  expect(navigation.querySelectorAll("button")).toHaveLength(6);
  const core = screen.getByRole("navigation", { name: "Workspace views" });
  expect(core.querySelectorAll("button")).toHaveLength(3);
  expect(core.querySelectorAll("a")).toHaveLength(1);
  expect(document.querySelector(".workspace-sidebar")).toBeNull();
  for (const label of [
    "Farm weather",
    "Crop Doctor",
    "Market prices",
    "Farm support",
    "Farm notebook",
    "Farmer exchange",
  ])
    expect(screen.getByRole("button", { name: label })).not.toHaveAttribute(
      "title",
    );
  fireEvent.click(screen.getByRole("button", { name: "Market prices" }));
  expect(screen.getByRole("button", { name: "Market prices" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(
    screen.getAllByRole("link", { name: "Back to classic interface" }),
  ).toHaveLength(1);
  expect(
    screen.getByRole("link", { name: "Back to classic interface" }),
  ).toHaveAttribute("href", "/overview");
});
