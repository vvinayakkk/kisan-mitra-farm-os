import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ClassicWorkspaceSwitch } from "./ClassicWorkspaceSwitch";
import { classicDestination, classicWorkspaceViews } from "@/lib/workspaceNavigation";
afterEach(cleanup);
it.each(Object.entries(classicWorkspaceViews))("offers one matching switch on /%s and returns to its origin", (origin, view) => {
  render(<MemoryRouter initialEntries={[`/${origin}`]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ClassicWorkspaceSwitch /></MemoryRouter>);
  const links = screen.getAllByRole("link", { name: "Switch to new interface" });
  expect(links).toHaveLength(1);
  expect(links[0]).toHaveAttribute("href", `/workspace?view=${view}&from=${origin}`);
  expect(classicDestination(origin)).toBe(`/${origin}`);
});
it.each(["/workspace", "/login", "/signup", "/", "/unknown"])("does not show a classic switch on %s", (path) => {
  render(<MemoryRouter initialEntries={[path]}><ClassicWorkspaceSwitch /></MemoryRouter>);
  expect(screen.queryByRole("link")).toBeNull();
});
it("rejects arbitrary classic return destinations", () => {
  for (const origin of ["//external.test", "toString", "__proto__", "unknown", null]) expect(classicDestination(origin)).toBe("/advisor");
});
