import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ExchangeMitra } from "./ExchangeMitra";
import { exchangeRequest } from "@/lib/exchangeClient";
vi.mock("@/lib/exchangeClient", () => ({ exchangeRequest: vi.fn() }));
vi.mock("@/components/WorkspaceVoiceField", () => ({
  WorkspaceVoiceField: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
function ask(text: string) {
  fireEvent.change(
    screen.getByRole("textbox", { name: "Ask exchange Mitra" }),
    { target: { value: text } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Ask Mitra" }));
}
describe("Exchange Mitra", () => {
  beforeEach(() => vi.clearAllMocks());
  it("keeps AI drafts unsaved until the farmer chooses the review editor", async () => {
    const draft = {
      kind: "listing" as const,
      fields: { title: "Sprayer", kind: "offer" as const },
    };
    vi.mocked(exchangeRequest).mockResolvedValue({
      answer: "Review the offer",
      draft,
      saved: false,
      questions: ["Which district?"],
    });
    const useDraft = vi.fn();
    render(<ExchangeMitra onUseDraft={useDraft} />);
    ask("I have a sprayer");
    await screen.findByText("Which district?");
    expect(useDraft).not.toHaveBeenCalled();
    expect(screen.getByText("REVIEWABLE DRAFT · NOT SAVED")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Review this draft/ }));
    expect(useDraft).toHaveBeenCalledWith(draft);
    expect(
      screen.getByRole("button", { name: /Added to review/ }),
    ).toBeDisabled();
  });
  it("retains farmer facts when answering a follow-up and resets on context change", async () => {
    vi.mocked(exchangeRequest).mockResolvedValue({
      answer: "How many days?",
      questions: ["Which district?"],
      saved: false,
    });
    const { rerender } = render(<ExchangeMitra intent="prepare_listing" />);
    ask("I have a sprayer");
    await screen.findByText("How many days?");
    ask("Two days in Ludhiana");
    await waitFor(() => expect(exchangeRequest).toHaveBeenCalledTimes(2));
    const options = vi.mocked(exchangeRequest).mock.calls[1][1];
    expect(JSON.parse(options?.body as string).message).toBe(
      "I have a sprayer\nFarmer follow-up: Two days in Ludhiana",
    );
    await screen.findByRole("button", { name: "Start a new brief" });
    rerender(
      <ExchangeMitra
        intent="review_exchange"
        conversationId="conversation-2"
      />,
    );
    expect(screen.queryByText("How many days?")).toBeNull();
    ask("Review the handover");
    await waitFor(() => expect(exchangeRequest).toHaveBeenCalledTimes(3));
    expect(
      JSON.parse(vi.mocked(exchangeRequest).mock.calls[2][1]?.body as string)
        .message,
    ).toBe("Review the handover");
  });
  it("discards late cancelled answers", async () => {
    let finish!: (value: unknown) => void;
    vi.mocked(exchangeRequest).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    render(<ExchangeMitra />);
    ask("Find a sprayer");
    fireEvent.click(
      screen.getByRole("button", { name: "Cancel Mitra request" }),
    );
    finish({ answer: "Cancelled advice", saved: false });
    await waitFor(() =>
      expect(screen.queryByText("Cancelled advice")).toBeNull(),
    );
    expect(screen.getByRole("button", { name: "Ask Mitra" })).toBeTruthy();
  });
  it("offers an explicit contextual close without clearing a typed brief", () => {
    const close = vi.fn();
    render(<ExchangeMitra compact onClose={close} />);
    fireEvent.change(
      screen.getByRole("textbox", { name: "Ask exchange Mitra" }),
      { target: { value: "What is missing before handover?" } },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Close exchange Mitra" }),
    );
    expect(close).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("textbox", { name: "Ask exchange Mitra" }),
    ).toHaveValue("What is missing before handover?");
  });
});
