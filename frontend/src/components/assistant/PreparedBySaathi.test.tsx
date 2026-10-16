import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ request: vi.fn(), owner: "farmer-a", ready: true }));
vi.mock("@/lib/farmWorkspaceClient", () => ({ workspaceRequest: mocks.request }));
vi.mock("@/lib/assistantClient", () => ({ getAssistantSessionId: () => mocks.owner, useAssistant: () => ({ready: mocks.ready}) }));
vi.mock("@/components/WorkspaceVoiceField", () => ({ WorkspaceVoiceField: ({children}: {children: React.ReactNode}) => <div>{children}</div> }));
import { PreparedBySaathi } from "./PreparedBySaathi";
import { invalidateWorkspaceCaches } from "@/lib/workspaceCacheLifecycle";
const proposal = (overrides = {}) => ({id: "proposal-1", title: "Plan the next sowing", summary: "A plan from your farm records.", steps: [{title: "Check soil moisture"}, {title: "Compare suitable crops"}], status: "draft", row_version: 7, created_at: "2026-10-15T09:00:00Z", evidence: [], ...overrides});
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
const open = () => fireEvent.click(screen.getByRole("button", {name: /PREPARED BY SAATHI/}));
beforeEach(() => {
  vi.useFakeTimers(); mocks.request.mockReset(); mocks.owner = "farmer-a"; mocks.ready = true;
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  vi.stubGlobal("IntersectionObserver", class {
    constructor(private callback: IntersectionObserverCallback) {}
    observe(target: Element) { this.callback([{isIntersecting: true, target} as IntersectionObserverEntry], this as unknown as IntersectionObserver); }
    disconnect() {} unobserve() {} takeRecords() { return []; }
  });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });
describe("Prepared by Saathi", () => {
  it("shows the proposal title collapsed and expands its actual steps", async () => {
    mocks.request.mockResolvedValue({proposals: [proposal()]}); render(<PreparedBySaathi area="records"/>); await flush();
    const heading = screen.getByRole("button", {name: /Plan the next sowing/});
    expect(heading).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Check soil moisture")).not.toBeInTheDocument();
    fireEvent.click(heading); expect(screen.getByText("Check soil moisture")).toBeInTheDocument();
    expect(mocks.request).toHaveBeenCalledWith("/api/companion/proposals?area=records", "GET", undefined, expect.objectContaining({fresh: true, signal: expect.any(AbortSignal)}));
  });
  it("prepares an empty area and polls queued work until a proposal is ready", async () => {
    let reads = 0;
    mocks.request.mockImplementation(async (_path, method) => method === "POST" ? {state: "queued"} : ++reads === 1 ? {proposals: []} : {proposals: [proposal()], job: {state: "completed"}});
    render(<PreparedBySaathi area="markets"/>); await flush();
    expect(mocks.request).toHaveBeenCalledWith("/api/companion/prepare", "POST", {area: "markets"}, expect.objectContaining({signal: expect.any(AbortSignal)}));
    expect(screen.getByText("Reviewing your farm…")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(screen.getByText("Plan the next sowing")).toBeInTheDocument();
    expect(mocks.request.mock.calls.filter(call => call[1] === "POST")).toHaveLength(1);
  });
  it("approves an edited draft with its row version and trimmed steps", async () => {
    mocks.request.mockResolvedValue({proposals: [proposal()]}); render(<PreparedBySaathi area="records"/>); await flush(); open();
    fireEvent.click(screen.getByRole("button", {name: "Edit"}));
    fireEvent.change(screen.getByRole("textbox", {name: "Plan title"}), {target: {value: "My sowing plan"}});
    fireEvent.change(screen.getByRole("textbox", {name: /Steps, one per line/}), {target: {value: " Check the field \n\n Order seed "}});
    fireEvent.click(screen.getByRole("button", {name: "Approve plan"})); await flush();
    expect(mocks.request).toHaveBeenCalledWith("/api/companion/proposals/proposal-1/review", "POST", {action: "approve", row_version: 7, title: "My sowing plan", steps: ["Check the field", "Order seed"]});
  });
  it("dismisses a proposal without attaching unsaved edit fields", async () => {
    mocks.request.mockResolvedValue({proposals: [proposal()]}); render(<PreparedBySaathi area="records"/>); await flush(); open();
    fireEvent.click(screen.getByRole("button", {name: "Edit"}));
    fireEvent.change(screen.getByRole("textbox", {name: "Plan title"}), {target: {value: "Unsaved"}});
    fireEvent.click(screen.getByRole("button", {name: "Dismiss"})); await flush();
    expect(mocks.request).toHaveBeenCalledWith("/api/companion/proposals/proposal-1/review", "POST", {action: "dismiss", row_version: 7});
  });
  it("surfaces read and review failures and preserves the edited input for retry", async () => {
    mocks.request.mockRejectedValueOnce(new Error("Cannot load proposals"));
    render(<PreparedBySaathi area="schemes"/>); await flush(); expect(screen.getByRole("alert")).toHaveTextContent("Cannot load proposals");
    mocks.request.mockResolvedValue({proposals: [proposal()]});
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); }); open();
    fireEvent.click(screen.getByRole("button", {name: "Edit"})); fireEvent.change(screen.getByRole("textbox", {name: "Plan title"}), {target: {value: "Keep my draft"}});
    mocks.request.mockRejectedValueOnce(new Error("This proposal changed elsewhere"));
    fireEvent.click(screen.getByRole("button", {name: "Approve plan"})); await flush();
    expect(screen.getByRole("alert")).toHaveTextContent("changed elsewhere");
    expect(screen.getByRole("textbox", {name: "Plan title"})).toHaveValue("Keep my draft");
  });
  it("aborts the active read and ignores its result after unmount", async () => {
    let finish!: (value: unknown) => void;
    mocks.request.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const view = render(<PreparedBySaathi area="markets"/>); await flush();
    const signal = mocks.request.mock.calls[0][3].signal as AbortSignal;
    view.unmount(); expect(signal.aborted).toBe(true);
    finish({proposals: []}); await flush(); expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it("requests grounded research explicitly and reports a preparation failure", async () => {
    mocks.request.mockResolvedValue({proposals: [proposal()]}); render(<PreparedBySaathi area="schemes"/>); await flush(); open();
    mocks.request.mockRejectedValueOnce(new Error("Research provider unavailable"));
    fireEvent.click(screen.getByRole("button", {name: "Research the web"})); await flush();
    expect(mocks.request).toHaveBeenCalledWith("/api/companion/prepare", "POST", {area: "schemes", research: true});
    expect(screen.getByRole("alert")).toHaveTextContent("Research provider unavailable");
    expect(screen.getByRole("button", {name: "Research the web"})).toBeEnabled();
  });
  it("offers retry for failed preparation and does not spin up an automatic retry loop", async () => {
    mocks.request.mockResolvedValue({proposals: [], job: {state: "failed", safe_error: "Provider timed out"}});
    render(<PreparedBySaathi area="markets"/>); await flush(); open();
    expect(screen.getByRole("alert")).toHaveTextContent("Preparation was interrupted");
    expect(screen.getByRole("button", {name: "Refresh"})).toBeEnabled();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(mocks.request.mock.calls.filter(call => call[1] === "POST")).toHaveLength(0);
    expect(mocks.request).toHaveBeenCalledTimes(2);
  });
  it("ignores a previous farmer's response instead of preparing for the new farmer", async () => {
    let finish!: (value: unknown) => void;
    mocks.request.mockImplementation(() => new Promise(resolve => {finish=resolve;}));
    render(<PreparedBySaathi area="records"/>); await flush(); mocks.owner = "farmer-b";
    finish({proposals: [proposal()]}); await flush();
    expect(screen.queryByText("Plan the next sowing")).not.toBeInTheDocument(); expect(mocks.request).toHaveBeenCalledTimes(1);
  });
  it("retains the draft's original row version when polling receives an external edit", async () => {
    let reads = 0;
    mocks.request.mockImplementation(async (_path, method) => method === "POST" ? {} : {proposals: [proposal(++reads > 1 ? {row_version: 8, title: "Changed elsewhere"} : {})]});
    render(<PreparedBySaathi area="records"/>); await flush(); open();
    fireEvent.click(screen.getByRole("button", {name: "Edit"}));
    fireEvent.change(screen.getByRole("textbox", {name: "Plan title"}), {target: {value: "My original draft"}});
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(screen.getByRole("textbox", {name: "Plan title"})).toHaveValue("My original draft");
    fireEvent.click(screen.getByRole("button", {name: "Approve plan"})); await flush();
    expect(mocks.request).toHaveBeenCalledWith("/api/companion/proposals/proposal-1/review", "POST", expect.objectContaining({action: "approve", row_version: 7, title: "My original draft"}));
  });
  it("does not cancel and repost its own automatic preparation on cache invalidation", async () => {
    mocks.request.mockImplementation(async (_path, method) => {
      if (method === "POST") {invalidateWorkspaceCaches("mutation"); return {state: "queued"};}
      return {proposals: []};
    });
    render(<PreparedBySaathi area="markets"/>); await flush();
    expect(screen.getByText("Reviewing your farm…")).toBeInTheDocument();
    expect(mocks.request).toHaveBeenCalledTimes(2);
    expect((mocks.request.mock.calls[0][3].signal as AbortSignal).aborted).toBe(false);
  });
  it("ignores a review error from the previous farmer after a session switch", async () => {
    let rejectReview!: (error: Error) => void;
    mocks.request.mockImplementation(async (_path, method) => method === "POST" ? new Promise((_resolve, reject) => {rejectReview=reject;}) : {proposals: [proposal({title: mocks.owner === "farmer-a" ? "Old farmer plan" : "New farmer plan"})]});
    const view = render(<PreparedBySaathi area="records"/>); await flush(); open();
    fireEvent.click(screen.getByRole("button", {name: "Approve plan"})); await flush();
    mocks.owner = "farmer-b"; view.rerender(<PreparedBySaathi area="records"/>); await flush();
    rejectReview(new Error("Old farmer private error")); await flush();
    expect(screen.queryByText("Old farmer private error")).not.toBeInTheDocument();
    expect(screen.getByText("New farmer plan")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: "Approve plan"})).toBeEnabled();
  });
  it("does not refetch after an unmounted manual preparation completes", async () => {
    let finish!: (value: unknown) => void;
    mocks.request.mockImplementation(async (_path, method) => method === "POST" ? new Promise(resolve => {finish=resolve;}) : {proposals: [proposal()]});
    const view = render(<PreparedBySaathi area="markets"/>); await flush(); open();
    fireEvent.click(screen.getByRole("button", {name: "Research the web"})); await flush(); view.unmount();
    finish({state: "queued"}); await flush();
    expect(mocks.request).toHaveBeenCalledTimes(2);
  });
  it("does not fetch an inactive feature", async () => {
    render(<PreparedBySaathi area="records" active={false}/>); await flush();
    expect(mocks.request).not.toHaveBeenCalled();
  });
});
