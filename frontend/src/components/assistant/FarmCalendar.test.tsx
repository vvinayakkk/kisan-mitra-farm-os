import {
  fireEvent,
  render,
  screen,
  cleanup,
  act,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FarmCalendar } from "./FarmCalendar";
const send = vi.hoisted(() => vi.fn());
const mutate = vi.hoisted(() => vi.fn(async () => undefined));
vi.mock("./AssistantChat", () => ({
  AssistantChat: () => <textarea aria-label="Compact calendar assistant" />,
}));
vi.mock("@/lib/assistantClient", () => ({
  useAssistant: () => ({
    tasks: [
      {
        id: "task",
        title: "Inspect field",
        due_date: "2026-10-15",
        notes: "Check lower leaves",
        completed: false,
      },
    ],
    running: false,
    pending: null,
  }),
  sendAssistant: send,
  changeTask: mutate,
}));
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-14T12:00:00"));
  send.mockClear();
  mutate.mockClear();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
it("shows saved task details on its date and completes it in place", async () => {
  const onChat = vi.fn();
  render(<FarmCalendar onChat={onChat} />);
  fireEvent.click(screen.getByRole("button", { name: "2026-10-15" }));
  expect(screen.getByText("Check lower leaves")).toBeInTheDocument();
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Mark done" })),
  );
  expect(mutate).toHaveBeenCalledWith(
    expect.objectContaining({ completed: true }),
    "edit",
  );
  expect(onChat).not.toHaveBeenCalled();
});
it("navigates months and creates a task for the explicitly selected date", () => {
  const onChat = vi.fn();
  render(<FarmCalendar onChat={onChat} />);
  fireEvent.click(screen.getByRole("button", { name: "Next month" }));
  expect(screen.getByText("November 2026")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "2026-11-03" }));
  fireEvent.click(screen.getByRole("button", { name: "Add task" }));
  expect(send).toHaveBeenCalledWith(expect.stringContaining("2026-11-03"));
});

it("edits a dated task and offers recovery after deletion", async () => {
  render(<FarmCalendar onChat={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "2026-10-15" }));
  fireEvent.click(screen.getByRole("button", { name: "Edit Inspect field" }));
  fireEvent.change(screen.getByLabelText("Task name"), {
    target: { value: "Inspect north field" },
  });
  fireEvent.change(screen.getByLabelText("Date"), {
    target: { value: "2026-10-16" },
  });
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Save changes" })),
  );
  expect(mutate).toHaveBeenCalledWith(
    expect.objectContaining({
      title: "Inspect north field",
      due_date: "2026-10-16",
    }),
    "edit",
  );
  await act(async () =>
    fireEvent.click(
      screen.getByRole("button", { name: "Delete Inspect field" }),
    ),
  );
  expect(screen.getByRole("status")).toHaveTextContent("Task removed.");
  await act(async () =>
    fireEvent.click(screen.getByRole("button", { name: "Undo" })),
  );
  expect(mutate).toHaveBeenLastCalledWith(
    expect.objectContaining({ id: "task" }),
    "restore",
  );
});
