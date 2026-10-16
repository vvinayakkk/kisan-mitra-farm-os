import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MitraHelper } from "./MitraHelper";
vi.mock("./AssistantChat", () => ({
  AssistantChat: ({ context }: { context: string }) => (
    <textarea aria-label={`${context} helper input`} />
  ),
}));
afterEach(cleanup);
it("keeps the station helper small until opened and preserves its draft when closed", () => {
  render(<MitraHelper context="station" collapsible />);
  const button = screen.getByRole("button", {
    name: "A little help from Mitra",
  });
  expect(button).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  fireEvent.click(button);
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "Check my readings" } });
  fireEvent.click(button);
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  fireEvent.click(button);
  expect(screen.getByRole("textbox")).toHaveValue("Check my readings");
});
it("uses the same simple helper for a feature page", () => {
  render(<MitraHelper context="markets" />);
  expect(
    screen.getByRole("textbox", { name: "markets helper input" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
