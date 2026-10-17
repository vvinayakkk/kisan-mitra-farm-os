import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
const state = vi.hoisted(() => ({ ready: true, loading: false, running: false, error: null, pending: null, status: "", messages: [{ id: "user", role: "user", text: "Check the weather", activities: [] }, { id: "reply", role: "assistant", text: "Your latest weather response stays here.", activities: [] }], artifacts: Array.from({ length: 13 }, (_, i) => ({ id: `file${i}`, file_id: `file${i}`, title: `Report ${i}`, format: "pdf", filename: `Report ${i}.pdf`, size: 1000 })), tasks: Array.from({ length: 8 }, (_, i) => ({ id: `task${i}`, title: `Farm task ${i}`, due_date: "2026-10-15", completed: false })), attachments: [], conversations: [], catalog: { skills: [], tools: [] } }));
vi.mock("@/lib/assistantClient", () => ({ getAssistantSessionId: () => "test-chat-session", useAssistant: () => state, initializeAssistant: vi.fn(), newConversation: vi.fn(), sendAssistant: vi.fn(), stopAssistant: vi.fn(), uploadAttachment: vi.fn(), downloadArtifact: vi.fn(), restoreConversation: vi.fn() }));
const localDrafts = vi.hoisted(() => ({ files: [] as any[] }));
vi.mock("@/lib/offlineStore", () => ({ offlineEnabled: () => true }));
vi.mock("@/lib/attachmentDrafts", () => ({
  listAttachmentDrafts: vi.fn(async () => localDrafts.files),
  storeAttachmentDraft: vi.fn(async (session: string, file: File) => { const saved = { id: 'local-only', session, name: file.name, type: file.type, size: file.size, createdAt: Date.now(), blob: file }; localDrafts.files = [saved]; return saved; }),
  readAttachmentDraft: vi.fn(async () => new File(['photo'], 'leaf.jpg', { type: 'image/jpeg' })),
  removeAttachmentDraft: vi.fn(async () => { localDrafts.files = []; window.dispatchEvent(new Event('skyview-attachment-drafts-change')); }),
}));
import { storeAttachmentDraft } from '@/lib/attachmentDrafts';
import { uploadAttachment, sendAssistant } from '@/lib/assistantClient';
vi.mock("./CompanionPanel", () => ({
  CompanionAvatar: () => <span />,
  CompanionPanel: ({ open, onClose, onVoice }: { open: boolean; onClose: () => void; onVoice: () => void }) => open ? <aside aria-label="Your farm companion"><button onClick={onClose}>Close companion</button><button onClick={onVoice}>Talk</button></aside> : null,
}));
import { AssistantChat } from "./AssistantChat";
beforeEach(() => { localDrafts.files = []; vi.clearAllMocks(); vi.stubGlobal("requestAnimationFrame", (fn: FrameRequestCallback) => setTimeout(() => fn(0), 0)); vi.stubGlobal("cancelAnimationFrame", (id: number) => clearTimeout(id)); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it("keeps persistent libraries closed while retaining every saved item", async () => {
  render(<AssistantChat />);
  await act(async () => {});
  expect(screen.getByText("Your latest weather response stays here.")).toBeInTheDocument();
  const files = screen.getByLabelText("Your files, 13 saved files").closest("details")!;
  const plan = screen.getByLabelText("Your farm plan, 8 tasks").closest("details")!;
  expect(files).not.toHaveAttribute("open"); expect(plan).not.toHaveAttribute("open");
  expect(files.querySelectorAll("button")).toHaveLength(13); expect(plan.querySelectorAll("article")).toHaveLength(8);
  fireEvent.click(screen.getByLabelText("Your files, 13 saved files"));
  expect(files).toHaveAttribute("open"); expect(screen.getByRole("button", { name: /Report 12/ })).toBeVisible();
});
it("collapses saved libraries when a new farmer request arrives", async () => {
  const { rerender } = render(<AssistantChat />);
  await act(async () => {});
  const files = screen.getByLabelText("Your files, 13 saved files").closest("details")!;
  fireEvent.click(screen.getByLabelText("Your files, 13 saved files")); expect(files).toHaveAttribute("open");
  state.messages = [...state.messages, { id: "new-request", role: "user", text: "Another question", activities: [] }];
  rerender(<AssistantChat />); expect(files).not.toHaveAttribute("open");
});

it("keeps offline files visibly local and uploads only after a separate online click", async () => {
  const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
  vi.mocked(uploadAttachment).mockResolvedValue({ id: 'server-attachment', name: 'leaf.jpg', format: 'jpg', characters: 0, truncated: false });
  const { container } = render(<AssistantChat />);
  const file = new File(['photo'], 'leaf.jpg', { type: 'image/jpeg' });
  await act(async () => { fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } }); });
  expect(await screen.findByText('Not uploaded · Upload when online')).toBeInTheDocument();
  expect(storeAttachmentDraft).toHaveBeenCalledWith('test-chat-session', file);
  expect(uploadAttachment).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: 'Upload now' })).toBeDisabled();
  await act(async () => { online.mockReturnValue(true); fireEvent(window, new Event('online')); });
  expect(uploadAttachment).not.toHaveBeenCalled();
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Upload now' })); });
  const { waitFor } = await import('@testing-library/react');
  await waitFor(() => expect(screen.queryByText('Not uploaded · Upload when online')).not.toBeInTheDocument());
  expect(uploadAttachment).toHaveBeenCalledOnce();
  expect(vi.mocked(uploadAttachment).mock.calls[0][0]).toBeInstanceOf(File);
  expect(sendAssistant).not.toHaveBeenCalled();
});
it("shows failed transfer honestly and retains the local copy", async () => {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
  localDrafts.files = [{ id: 'local-only', session: 'test-chat-session', name: 'leaf.jpg', size: 5, createdAt: Date.now(), blob: new Blob(['photo']) }];
  vi.mocked(uploadAttachment).mockRejectedValue(new Error('Upload unavailable; nothing was stored on the server.'));
  render(<AssistantChat />);
  await screen.findByText('Not uploaded · Upload when online');
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Upload now' })); });
  expect(await screen.findByRole('alert')).toHaveTextContent('nothing was stored on the server');
  expect(screen.getByText('Not uploaded · Upload when online')).toBeInTheDocument();
  expect(sendAssistant).not.toHaveBeenCalled();
});
it("renders reviewed mission steps as readable content rather than object strings", async () => {
  (state as any).pending = {id:'approval',kind:'approval',tool:'create_mission',arguments:{title:'Field check',steps:[{title:'Inspect the field',done:false}]}};
  render(<AssistantChat/>); await act(async()=>{});
  expect(screen.getByText('Save this longer farm plan?')).toBeInTheDocument();
  expect(screen.getByText('Inspect the field')).toBeInTheDocument();
  expect(screen.queryByText('[object Object]')).not.toBeInTheDocument();
  (state as any).pending = null;
});

it("asks for one detail at a time, preserves earlier answers, and sends them together", async () => {
  (state as any).pending = {
    id: "weekly-plan-questions",
    kind: "question",
    tool: "ask_farmer",
    arguments: {
      question: "Let's plan your week.",
      fields: [
        { id: "crop", label: "Which crop?", type: "text", options: [] },
        { id: "stage", label: "Growth stage", type: "select", options: ["Flowering", "Harvest"] },
        { id: "workers", label: "Available workers", type: "number", options: [] },
      ],
    },
  };
  try {
    render(<AssistantChat />);
    await act(async () => {});
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByLabelText("Which crop?")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Growth stage" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Which crop?"), { target: { value: "Groundnut" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.queryByLabelText("Which crop?")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Flowering" }));
    expect(screen.getByRole("button", { name: "Flowering" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByLabelText("Which crop?")).toHaveValue("Groundnut");
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    expect(screen.getByRole("button", { name: "Flowering" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Continue/ }));
    fireEvent.change(screen.getByLabelText("Available workers"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /Send answers/ }));
    expect(sendAssistant).toHaveBeenCalledWith(
      "Which crop?: Groundnut · Growth stage: Flowering · Available workers: 3",
      { answers: { crop: "Groundnut", stage: "Flowering", workers: "3" }, pending_id: "weekly-plan-questions" },
    );
  } finally {
    (state as any).pending = null;
  }
});

it('opens history beside the conversation without hiding the composer or its draft', async () => {
  render(<AssistantChat />);
  await act(async () => {});
  const input = screen.getByRole('textbox', { name: 'Message Kisan Mitra' });
  const conversation = screen.getByRole('log', { name: 'Conversation' });
  fireEvent.change(input, { target: { value: 'Keep my draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Previous conversations' }));
  const panel = screen.getByRole('dialog', { name: 'Chat history' });
  expect(conversation).not.toContainElement(panel);
  expect(input).toHaveValue('Keep my draft');
  fireEvent.click(screen.getByRole('button', { name: 'Close history' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(input).toHaveValue('Keep my draft');
});

it('opens skills and tools in the same side panel and switches the catalogue tab', async () => {
  render(<AssistantChat />);
  await act(async () => {});
  fireEvent.click(screen.getByRole('button', { name: /Skills & tools/ }));
  expect(screen.getByRole('dialog', { name: 'Skills and tools' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Tools ·/ }));
  expect(screen.getByRole('button', { name: /Tools ·/ })).toHaveClass('selected');
  fireEvent.click(screen.getByRole('button', { name: 'Close skills' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

 it('hides the side panel when another workspace view becomes active', async () => {
  const { rerender } = render(<AssistantChat active />);
  await act(async () => {});
  fireEvent.click(screen.getByRole('button', { name: 'Previous conversations' }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  rerender(<AssistantChat active={false} />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

it("opens Saathi over a non-chat page without navigating or inheriting the hidden chat container", async () => {
  const anchor = document.createElement("div");
  document.body.append(anchor);
  const onVoice = vi.fn();
  const page = render(<div style={{ display: "none" }}><AssistantChat active={false} companionAnchor={anchor} onCompanionVoice={onVoice} /></div>);
  await act(async () => {});
  fireEvent.click(screen.getByRole("button", { name: "Your farm companion" }));
  expect(screen.getByRole("complementary", { name: "Your farm companion" })).toBeVisible();
  expect(onVoice).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Close companion" }));
  expect(screen.queryByRole("complementary", { name: "Your farm companion" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Your farm companion" })).toHaveFocus();
  page.unmount(); anchor.remove();
});

it("accepts a written answer alongside suggested choices", async () => {
  (state as any).pending = {id:"custom-question",kind:"question",arguments:{fields:[{id:"water",type:"select",label:"Water source",options:["Well","Canal"]}]}};
  render(<AssistantChat/>);
  fireEvent.change(await screen.findByLabelText("Or type your own answer"),{target:{value:"Shared rainwater tank"}});
  fireEvent.submit(screen.getByLabelText("Or type your own answer").closest("form")!);
  expect(sendAssistant).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({answers:{water:"Shared rainwater tank"},pending_id:"custom-question"}));
  (state as any).pending=null;
});
