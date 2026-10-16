import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { FarmNotebook } from "./FarmNotebook";
import type { NotebookTab } from "./FarmWorkspace";
vi.mock("./MitraHelper", () => ({ MitraHelper: () => <button>Ask Mitra</button> }));
afterEach(cleanup);
function Journal() {
  const [tab, setTab] = useState<NotebookTab>("today");
  return <FarmNotebook tab={tab} onChange={setTab}><p>{tab} records</p></FarmNotebook>;
}
it("turns pages and keeps tab labels, panel and page controls in sync", () => {
  render(<Journal />);
  expect(screen.getByRole("button", { name: "Previous notebook page" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Next notebook page" }));
  expect(screen.getByRole("tabpanel", { name: "02 My fields" })).toHaveTextContent("fields records");
  fireEvent.click(screen.getByRole("tab", { name: "07 Files" }));
  expect(screen.getByRole("button", { name: "Next notebook page" })).toBeDisabled();
  expect(screen.getByRole("tabpanel", { name: "07 Files" })).toHaveTextContent("files records");
});
it("supports arrow and Home/End navigation with focus following the selected page", () => {
  render(<Journal />);
  fireEvent.keyDown(screen.getByRole("tab", { name: "01 Today" }), { key: "ArrowDown" });
  expect(screen.getByRole("tab", { name: "02 My fields" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "End" });
  expect(screen.getByRole("tab", { name: "07 Files" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "Home" });
  expect(screen.getByRole("tab", { name: "01 Today" })).toHaveFocus();
});
