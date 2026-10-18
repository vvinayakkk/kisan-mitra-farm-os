import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import {
  useAssistant,
  sendAssistant,
  uploadAttachment,
} from "./assistantClient";
afterEach(() => vi.unstubAllGlobals());
function stream(events: object[]) {
  const bytes = new TextEncoder().encode(
    events.map((e) => JSON.stringify(e)).join("\n") + "\n",
  );
  return new Response(
    new ReadableStream({
      start(controller) {
        for (let i = 0; i < bytes.length; i += 7)
          controller.enqueue(bytes.slice(i, i + 7));
        controller.close();
      },
    }),
  );
}
it("handles fragmented UTF-8 streams, resumes a question and exposes real artifact results", async () => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => values.set(k, v),
    removeItem: (k: string) => values.delete(k),
  });
  vi.stubGlobal("requestAnimationFrame", (fn: FrameRequestCallback) =>
    setTimeout(() => fn(performance.now()), 0),
  );
  vi.stubGlobal("cancelAnimationFrame", (id: number) => clearTimeout(id));
  let pending: object | null = null;
  let runs = 0;
  const artifact = {
    id: "artifact",
    file_id: "f".repeat(32),
    title: "Farm budget",
    format: "xlsx",
    filename: "Farm budget.xlsx",
    size: 5200,
  };
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, options?: RequestInit) => {
      const path = new URL(input, "http://localhost").pathname;
      if (path.endsWith("/catalog"))
        return Response.json({ skills: [], tools: [] });
      if (path.endsWith("/sessions"))
        return Response.json({ id: "a".repeat(32), token: "session-token" });
      if (path.endsWith("/attachments-json"))
        return Response.json({
          id: "b".repeat(32),
          name: "public-test.png",
          format: "png",
          characters: 0,
          truncated: false,
        });
      if (path.endsWith("/run")) {
        bodies.push(JSON.parse(String(options?.body)));
        runs++;
        if (runs === 1) {
          pending = {
            id: "pending",
            kind: "question",
            tool: "ask_farmer",
            arguments: {
              question: "Which crop?",
              fields: [
                { id: "crop", label: "Crop", type: "text", options: [] },
                {
                  id: "photo",
                  label: "Crop photo",
                  type: "photo",
                  options: [],
                },
              ],
            },
          };
          return stream([
            { type: "delta", text: "I can help with ₹800." },
            { type: "question", pending },
            { type: "done", status: "waiting" },
          ]);
        }
        pending = null;
        return stream([
          {
            type: "tool_started",
            call_id: "file",
            tool: "create_file",
            label: "Creating your file",
          },
          {
            type: "tool_completed",
            call_id: "file",
            tool: "create_file",
            label: "Creating your file",
            result: { artifact },
            elapsed_ms: 12,
          },
          { type: "delta", text: "Your file is ready." },
          { type: "done", status: "completed" },
        ]);
      }
      return Response.json({
        messages: [],
        pending,
        artifacts: runs > 1 ? [artifact] : [],
        tasks: [],
      });
    }),
  );
  const { result } = renderHook(() => useAssistant());
  await waitFor(() => expect(result.current.ready).toBe(true));
  await act(async () => {
    await sendAssistant("Make a budget");
  });
  expect(
    result.current.messages[result.current.messages.length - 1]?.text,
  ).toBe("I can help with ₹800.");
  expect(result.current.pending?.id).toBe("pending");
  await act(async () => {
    await uploadAttachment(
      new File(["public synthetic upload fixture"], "public-test.png", {
        type: "image/png",
      }),
    );
  });
  expect(result.current.attachments[0].id).toBe("b".repeat(32));
  await act(async () => {
    await sendAssistant("Wheat", {
      answers: { crop: "Wheat", photo: "b".repeat(32) },
      pending_id: "pending",
    });
  });
  expect(bodies[1].answers).toEqual({ crop: "Wheat", photo: "b".repeat(32) });
  expect(bodies[1].pending_id).toBe("pending");
  expect(result.current.pending).toBeNull();
  expect(result.current.artifacts[0].file_id).toBe(artifact.file_id);
  expect(
    result.current.messages[result.current.messages.length - 1]?.activities[0]
      .status,
  ).toBe("done");
  expect(result.current.running).toBe(false);
});

it("dispatches capability revocation and clears local access even when offline", async () => {
  const { revokeAssistantSession, getAssistantSessionId } = await import("./assistantClient");
  const remove = vi.fn();
  vi.stubGlobal("localStorage", { getItem: () => JSON.stringify({ id: "a".repeat(32), token: "session-token" }), removeItem: remove, length: 0 });
  const fetch = vi.fn().mockRejectedValue(new Error("Offline")); vi.stubGlobal("fetch", fetch);
  await revokeAssistantSession();
  expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/revoke"), expect.objectContaining({ method: "POST", headers: { Authorization: "Bearer session-token", "X-Assistant-Session": "a".repeat(32) } }));
  expect(getAssistantSessionId()).toBeNull();
  expect(remove).toHaveBeenCalledWith(expect.stringContaining("skyview-assistant-session"));
});

it("does not let an old initialization overwrite a newly adopted farm", async () => {
  const { adoptAssistantSession, clearAssistantSession, getAssistantSessionId } = await import('./assistantClient');
  const { readSnapshot, setOfflineEnabled } = await import('./offlineStore');
  clearAssistantSession(); localStorage.clear(); setOfflineEnabled(true);
  const a = 'a'.repeat(32), b = 'b'.repeat(32);
  let release!: (response: Response) => void;
  const fetch = vi.fn(async (input: string, options?: RequestInit) => {
    const owner = new Headers(options?.headers).get('X-Assistant-Session');
    if (input.endsWith('/catalog') && owner === a) return new Promise<Response>(done => { release = done; });
    if (input.endsWith('/catalog')) return Response.json({ skills: [{ id: 'b-skill' }], tools: [] });
    return Response.json({ messages: [{ role: 'assistant', content: 'Farm B only' }], pending: null, artifacts: [], tasks: [] });
  });
  vi.stubGlobal('fetch', fetch);
  const old = adoptAssistantSession(a, 'A-token').catch(error => error);
  await waitFor(() => expect(release).toBeTypeOf('function'));
  await adoptAssistantSession(b, 'B-token');
  release(Response.json({ skills: [{ id: 'a-skill' }], tools: [] }));
  expect((await old).message).toContain('session changed');
  const { result, unmount } = renderHook(() => useAssistant());
  expect(getAssistantSessionId()).toBe(b);
  expect(result.current.ready).toBe(true);
  expect(result.current.catalog.skills[0].id).toBe('b-skill');
  expect(result.current.messages[0].text).toBe('Farm B only');
  expect(readSnapshot(a, 'assistant-session')).toBeNull();
  expect((await readSnapshot(b, 'assistant-session')!.json()).messages[0].content).toBe('Farm B only');
  unmount(); clearAssistantSession();
});

it("guards response decoding so an old session cannot write a new owner's offline cache", async () => {
  const { adoptAssistantSession, clearAssistantSession } = await import('./assistantClient');
  const { readSnapshot, setOfflineEnabled } = await import('./offlineStore');
  clearAssistantSession(); localStorage.clear(); setOfflineEnabled(true);
  const a = 'a'.repeat(32), b = 'b'.repeat(32);
  let release!: (data: unknown) => void;
  vi.stubGlobal('fetch', vi.fn(async (input: string, options?: RequestInit) => {
    const owner = new Headers(options?.headers).get('X-Assistant-Session');
    if (input.endsWith('/catalog')) return Response.json({ skills: [], tools: [] });
    if (owner === a) { const response = Response.json({}); response.json = () => new Promise(done => { release = done; }); return response; }
    return Response.json({ messages: [{ role: 'assistant', content: 'Farm B' }], pending: null, artifacts: [], tasks: [] });
  }));
  const old = adoptAssistantSession(a, 'A-token').catch(error => error);
  await waitFor(() => expect(release).toBeTypeOf('function'));
  await adoptAssistantSession(b, 'B-token');
  release({ messages: [{ role: 'assistant', content: 'Private Farm A' }], pending: null, artifacts: [], tasks: [] });
  expect((await old).message).toContain('session changed');
  expect((await readSnapshot(b, 'assistant-session')!.json()).messages[0].content).toBe('Farm B');
  const { result, unmount } = renderHook(() => useAssistant());
  expect(result.current.messages[0].text).toBe('Farm B');
  unmount(); clearAssistantSession();
});

it("restores opted-in offline history and catalog without restoring approvals or replaying writes", async () => {
  const { clearAssistantSession, initializeAssistant, assistantAuthHeaders } = await import('./assistantClient');
  const { saveSnapshot, setOfflineEnabled } = await import('./offlineStore');
  clearAssistantSession(); localStorage.clear(); setOfflineEnabled(true);
  const a = 'a'.repeat(32);
  localStorage.setItem('skyview-assistant-session-v1:' + (import.meta.env.VITE_ASSISTANT_API_URL ?? import.meta.env.VITE_API_URL ?? '').replace(/\/$/, ''), JSON.stringify({ id: a, token: 'offline-token' }));
  saveSnapshot(a, 'assistant-session', JSON.stringify({ messages: [{ role: 'assistant', content: 'Saved advice' }], tasks: [{ id: 'task', title: 'Check crop' }], artifacts: [], pending: { id: 'old-approval', kind: 'approval' } }));
  saveSnapshot(a, 'assistant-catalog', JSON.stringify({ skills: [{ id: 'stored-skill' }], tools: [] }));
  const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
  const fetch = vi.fn().mockRejectedValue(new TypeError('Offline')); vi.stubGlobal('fetch', fetch);
  await initializeAssistant();
  const { result, unmount } = renderHook(() => useAssistant());
  expect(result.current.ready).toBe(true);
  expect(result.current.pending).toBeNull();
  expect(result.current.messages[0].text).toBe('Saved advice');
  expect(result.current.catalog.skills[0].id).toBe('stored-skill');
  expect(result.current.error).toContain('Offline');
  expect((await assistantAuthHeaders())['X-Assistant-Session']).toBe(a);
  const count = fetch.mock.calls.length;
  await act(() => sendAssistant('Save an expense'));
  expect(fetch.mock.calls.length).toBe(count);
  online.mockRestore(); unmount(); clearAssistantSession();
});

it('cancels an attachment before reading bytes or dispatching a network write', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  const controller = new AbortController(); controller.abort();
  await expect(uploadAttachment(new File(['private'], 'photo.jpg'), controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
  expect(fetch).not.toHaveBeenCalled();
});

it('authorizes page reads with a saved session before chat hydration finishes', async () => {
  const { clearAssistantSession, assistantAuthHeaders, initializeAssistant } = await import('./assistantClient');
  clearAssistantSession(); localStorage.clear();
  const id = 'c'.repeat(32);
  const base = (import.meta.env.VITE_ASSISTANT_API_URL ?? import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
  localStorage.setItem('skyview-assistant-session-v1:' + base, JSON.stringify({id, token: 'saved-test-token'}));
  let finishCatalog!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn((url: string) => String(url).endsWith('/catalog')
    ? new Promise<Response>(resolve => { finishCatalog = resolve; })
    : Promise.resolve(Response.json({messages: [], tasks: [], artifacts: [], attachments: [], conversations: [], pending: null}))));
  expect(await assistantAuthHeaders()).toEqual({Authorization: 'Bearer saved-test-token', 'X-Assistant-Session': id});
  finishCatalog(Response.json({skills: [], tools: []}));
  await initializeAssistant();
  clearAssistantSession();
});
