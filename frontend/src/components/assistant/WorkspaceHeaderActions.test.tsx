import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { WorkspaceHeaderActions } from "./WorkspaceHeaderActions";
const { setLanguage } = vi.hoisted(() => ({ setLanguage: vi.fn() }));
vi.mock("@/contexts/LanguageContext", () => ({ useLanguage: () => ({ language: "en", setLanguage }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it("uses the existing language switch with native names and current selection", async () => {
  render(<WorkspaceHeaderActions />);
  fireEvent.keyDown(screen.getByRole("button", { name: "Change language" }), { key: "Enter" });
  expect(await screen.findByRole("menuitemradio", { name: "English" })).toHaveAttribute("aria-checked", "true");
  fireEvent.click(screen.getByRole("menuitemradio", { name: "తెలుగు" }));
  expect(setLanguage).toHaveBeenCalledWith("te");
});
it("shows a small inline number without opening a dialog", async () => {
  render(<WorkspaceHeaderActions />);
  expect(screen.queryByRole("link")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Call support agent" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(screen.getByLabelText("Support telephone")).toContainElement(screen.getByRole("link"));
  expect(screen.getByRole("link")).toHaveAttribute("href", "tel:+17754900454");
  fireEvent.click(screen.getByRole("button", { name: "Close call support" }));
  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.getByRole("button", { name: "Call support agent" })).toBeInTheDocument();
});
