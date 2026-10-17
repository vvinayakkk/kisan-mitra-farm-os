import { preferredLanguage, applyLanguagePreference } from "./languagePreference";
import { clearOfflineData, readSnapshot, saveSnapshot } from "./offlineStore";
import { useEffect, useSyncExternalStore } from "react";
import { workspaceReadCache } from "./workspaceReadCache";
import { invalidateWorkspaceCaches } from "./workspaceCacheLifecycle";
import { reportedMarketsOnly } from "./localPresentation";
import { currentIdentityToken, firebasePhoneEnabled } from "./firebasePhoneAuth";
export interface Artifact {
  id: string;
  file_id: string;
  title: string;
  format: string;
  filename: string;
  size: number;
  revision?: number;
  revision_of?: string | null;
  preview?: {
    title: string;
    sections: { heading: string; text: string }[];
    columns: string[];
    rows: (string | number | null)[][];
    row_count: number;
    partial: boolean;
  };
}
export interface FarmTask {
  id: string;
  title: string;
  due_date: string;
  notes?: string;
  completed: boolean;
  row_version?: number;
}
export interface Attachment {
  id: string;
  name: string;
  format: string;
  characters: number;
  truncated: boolean;
}
export interface Activity {
  call_id: string;
  tool: string;
  label: string;
  status: "running" | "done" | "error";
  result?: Record<string, unknown>;
  elapsed_ms?: number;
  error?: string;
}
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  activities: Activity[];
  status?: string;
  error?: string;
  serverId?: string;
}
export interface Pending {
  id: string;
  kind: "question" | "approval";
  review_labels?: Record<string, string>;
  tool: string;
  arguments: {
    question?: string;
    fields?: { id: string; label: string; type: string; options: string[] }[];
    [key: string]: unknown;
  };
}
interface Catalog {
  skills: {
    id: string;
    name: string;
    description: string;
    workflow?: string;
  }[];
  tools: { id: string; name: string; description: string; approval: boolean }[];
}
interface State {
  ready: boolean;
  loading: boolean;
  running: boolean;
  messages: ChatMessage[];
  pending: Pending | null;
  artifacts: Artifact[];
  tasks: FarmTask[];
  deletedTasks: FarmTask[];
  attachments: Attachment[];
  conversations: { id: string; title: string; created_at: string }[];
  catalog: Catalog;
  error: string | null;
  status: string;
}
const base = (
  import.meta.env.VITE_ASSISTANT_API_URL ??
  import.meta.env.VITE_API_URL ??
  ""
).replace(/\/$/, "");
let state: State = {
  ready: false,
  loading: false,
  running: false,
  messages: [],
  pending: null,
  artifacts: [],
  tasks: [],
  deletedTasks: [],
  attachments: [],
  conversations: [],
  catalog: { skills: [], tools: [] },
  error: null,
  status: "",
};
const subscribers = new Set<() => void>();
let session: { id: string; token: string } | null = null;
let initializing: Promise<void> | null = null;
let sessionGeneration = 0;
function assertCurrent(generation: number, owner = session): void {
  if (generation !== sessionGeneration || owner?.id !== session?.id || owner?.token !== session?.token)
    throw new Error("Your farm session changed. Please reopen this page.");
}
let controller: AbortController | null = null;
const key = "skyview-assistant-session-v1:" + base;
function update(patch: Partial<State>) {
  state = { ...state, ...patch };
  subscribers.forEach((fn) => fn());
}
async function request(path: string, options: RequestInit = {}) {
  const generation = sessionGeneration, owner = session;
  const identityToken = path === "/sessions" && firebasePhoneEnabled
    ? await currentIdentityToken()
    : null;
  const response = await fetch(base + "/api/assistant" + path, {
    ...options,
    headers: {
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(owner ? { Authorization: `Bearer ${owner.token}`, "X-Assistant-Session": owner.id } : {}),
      ...(identityToken ? { Authorization: `Bearer ${identityToken}` } : {}),
      ...options.headers,
    },
  });
  assertCurrent(generation, owner);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    assertCurrent(generation, owner);
    if (response.status === 409 && path.includes("/tasks/")) throw new Error("This task changed elsewhere. Reopen it to use the latest version.");
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Assistant request failed (${response.status}).`,
    );
  }
  if (options.method && options.method !== "GET" && !path.includes("/inspect/")) invalidateWorkspaceCaches();
  return response;
}
async function sync() {
  if (!session) return;
  const generation = sessionGeneration, owner = session;
  const data = await (await request(`/sessions/${owner.id}`)).json();
  assertCurrent(generation, owner);
  invalidateWorkspaceCaches();
  saveSnapshot(owner.id, "assistant-session", JSON.stringify(data));
  update({
    pending: data.pending,
    artifacts: data.artifacts,
    tasks: data.tasks,
    deletedTasks: data.deleted_tasks ?? [],
    attachments: data.attachments ?? [],
    conversations: data.conversations ?? [],
  });
  return data;
}
function readableHistory(text: string): string {
  text = text.replace(
    /^Calendar context: selected date \d{4}-\d{2}-\d{2}\. Farmer request: /,
    "",
  );
  if (!text.startsWith("Requested details: ")) return text;
  try {
    const values = JSON.parse(
      text.slice("Requested details: ".length),
    ).farmer_answers;
    return Object.entries(values)
      .map(([key, value]) => `${key.replace(/_/g, " ")}: ${String(value)}`)
      .join(" · ");
  } catch {
    return text;
  }
}
export async function initializeAssistant() {
  if (state.ready) return;
  if (initializing) return initializing;
  update({ loading: true, error: null });
  const generation = sessionGeneration;
  initializing = (async () => {
    try {
      let stored: string | null = null;
      try { stored = localStorage.getItem(key); } catch {                                             }
      if (stored) {
        try {
          const value = JSON.parse(stored);
          if (!session && typeof value.id === "string" && /^[a-f0-9]{32}$/.test(value.id) && typeof value.token === "string" && value.token)
            session = value;
        } catch {
          try { localStorage.removeItem(key); } catch {                            }
        }
      }
      const catalog = await (await request("/catalog")).json();
      assertCurrent(generation);
      if (!session) {
        const created = await (await request("/sessions", { method: "POST" })).json();
        assertCurrent(generation);
        session = created;
        try { localStorage.setItem(key, JSON.stringify(session)); } catch {                                      }
      }
      let data;
      try {
        data = await sync();
      } catch (error) {
        if (
          !(error instanceof Error) ||
          !error.message.includes("key is invalid")
        )
          throw error;
        const created = await (await request("/sessions", { method: "POST" })).json();
        assertCurrent(generation);
        session = created;
        try { localStorage.setItem(key, JSON.stringify(session)); } catch {                                      }
        data = await sync();
      }
      assertCurrent(generation);
      if (data.preferred_language && !localStorage.getItem('app_language')) applyLanguagePreference(data.preferred_language);
      if (session) saveSnapshot(session.id, "assistant-catalog", JSON.stringify(catalog));
      update({
        ready: true,
        loading: false,
        catalog,
        messages: (data.messages ?? []).map(
          (m: {
            id?: string;
            role: "user" | "assistant";
            content: string;
            activities?: Activity[];
            status?: string;
            error?: string;
          }) => ({
            id: m.id || crypto.randomUUID(),
            role: m.role,
            text: readableHistory(m.content),
            activities: m.activities || [],
            status: m.status,
            error: m.error,
          }),
        ),
      });
    } catch (error) {
      if (generation !== sessionGeneration) return;
      const cached = session && !navigator.onLine ? readSnapshot(session.id, "assistant-session") : null;
      const catalog = session && !navigator.onLine ? readSnapshot(session.id, "assistant-catalog") : null;
      if (cached && catalog) {
        const data = await cached.json(), tools = await catalog.json();
        if (generation !== sessionGeneration) return;
        update({ ready: true, loading: false, catalog: tools, pending: null, artifacts: data.artifacts ?? [], tasks: data.tasks ?? [], deletedTasks: [], attachments: [], conversations: [], messages: (data.messages ?? []).map((m: { id?: string; role: "user" | "assistant"; content: string; activities?: Activity[] }) => ({ id: m.id || crypto.randomUUID(), role: m.role, text: readableHistory(m.content), activities: m.activities || [] })), error: "Offline. Showing saved conversation and plan; reconnect before sending or saving changes." });
      } else update({
        loading: false,
        error:
          error instanceof Error
            ? error.message
            : "The assistant server could not be reached.",
      });
    } finally {
      if (generation === sessionGeneration) initializing = null;
    }
  })();
  return initializing;
}
function changeMessage(id: string, fn: (message: ChatMessage) => ChatMessage) {
  update({ messages: state.messages.map((m) => (m.id === id ? fn(m) : m)) });
}
export async function sendAssistant(
  message: string,
  extra: Record<string, unknown> = {},
) {
  if (state.running) return;
  const generation = sessionGeneration;
  if (!navigator.onLine) { update({ error: "You are offline. Your draft stays here; reconnect to send it." }); return; }
  if (!state.ready) await initializeAssistant();
  if (generation !== sessionGeneration || !session || !state.ready) return;
  const owner = session;
  const id = crypto.randomUUID();
  update({
    running: true,
    error: null,
    status: "Connecting",
    messages: [
      ...state.messages,
      { id: crypto.randomUUID(), role: "user", text: message, activities: [] },
      { id, role: "assistant", text: "", activities: [], status: "working" },
    ],
  });
  const activeController = new AbortController();
  controller = activeController;
  const timeout = window.setTimeout(
    () => activeController.abort("timeout"),
    180000,
  );
  let terminal = false;
  let deltaBuffer = "";
  let frame: number | null = null;
  const flush = () => {
    if (generation !== sessionGeneration) { deltaBuffer = ""; if (frame !== null) cancelAnimationFrame(frame); frame = null; return; }
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    if (deltaBuffer) {
      const text = deltaBuffer;
      deltaBuffer = "";
      changeMessage(id, (m) => ({ ...m, text: m.text + text }));
    }
  };
  try {
    const response = await request(`/sessions/${owner.id}/run`, {
      method: "POST",
      signal: activeController.signal,
      body: JSON.stringify({
        message,
        station_id: import.meta.env.VITE_STATION_ID || "WS01",
        language: preferredLanguage(),
        ...extra,
      }),
    });
    if (!response.body)
      throw new Error("This browser cannot read the response stream.");
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "";
    const consume = (line: string) => {
      assertCurrent(generation, owner);
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "delta") {
        deltaBuffer += event.text;
        if (frame === null) frame = requestAnimationFrame(flush);
      } else flush();
      if (event.type === "run_started") changeMessage(id, (m) => ({ ...m, serverId: event.run_id }));
      if (event.type === "status") update({ status: event.label });
      if (event.type === "tool_started") {
        update({ status: event.label });
        changeMessage(id, (m) => ({
          ...m,
          activities: [
            ...m.activities,
            {
              call_id: event.call_id,
              tool: event.tool,
              label: event.label,
              status: "running",
            },
          ],
        }));
      }
      if (event.type === "tool_completed" || event.type === "tool_failed") {
        if (event.type === "tool_completed") invalidateWorkspaceCaches();
        changeMessage(id, (m) => ({
          ...m,
          activities: m.activities.map((a) =>
            a.call_id === event.call_id
              ? {
                  ...a,
                  status: event.type === "tool_completed" ? "done" : "error",
                  result: event.result,
                  elapsed_ms: event.elapsed_ms,
                  error: event.error,
                }
              : a,
          ),
        }));
        if (event.result?.artifact)
          update({ artifacts: [event.result.artifact, ...state.artifacts] });
      }
      if (event.type === "question" || event.type === "approval")
        update({ pending: event.pending, status: "Waiting for you" });
      if (event.type === "error") {
        terminal = true;
        changeMessage(id, (m) => ({
          ...m,
          error: event.message,
          status: "error",
        }));
      }
      if (event.type === "done") {
        terminal = true;
        changeMessage(id, (m) => ({ ...m, status: event.status }));
      }
    };
    while (true) {
      const { value, done } = await reader.read();
      if (generation !== sessionGeneration) { void reader.cancel().catch(() => {}); return; }
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) consume(line);
    }
    buffer += decoder.decode();
    if (buffer.trim()) consume(buffer);
    if (!terminal)
      throw new Error("The response stopped before completion. Please retry.");
    await sync();
  } catch (error) {
    if (generation !== sessionGeneration) return;
    const aborted = activeController.signal.aborted;
    changeMessage(id, (m) => ({
      ...m,
      status: aborted ? "stopped" : "error",
      error: aborted
        ? activeController.signal.reason === "timeout"
          ? "The request timed out. Try a smaller task."
          : "Stopped. Any already saved files or tasks remain available."
        : error instanceof Error
          ? error.message
          : "The request failed.",
    }));
  } finally {
    flush();
    clearTimeout(timeout);
    if (controller === activeController) controller = null;
    if (generation === sessionGeneration) update({ running: false, status: "" });
  }
}
export function stopAssistant() {
  controller?.abort("user");
}
export async function newConversation() {
  if (state.running) return;
  const generation = sessionGeneration;
  if (session) {
    try {
      await request(`/sessions/${session.id}/reset`, { method: "POST" });
      assertCurrent(generation);
    } catch (error) {
      if (generation !== sessionGeneration) return;
      update({
        error:
          error instanceof Error
            ? error.message
            : "Could not start a new conversation.",
      });
      return;
    }
  }
  update({ ready: false, messages: [], pending: null, error: null });
  await initializeAssistant();
}
export async function restoreConversation(id: string) {
  if (state.running || !session) return;
  const generation = sessionGeneration;
  try {
    await request(`/sessions/${session.id}/restore/${id}`, { method: "POST" });
    assertCurrent(generation);
    update({ ready: false, error: null });
    await initializeAssistant();
  } catch (error) {
    if (generation !== sessionGeneration) return;
    update({
      error:
        error instanceof Error
          ? error.message
          : "Could not restore the conversation.",
    });
  }
}
export async function uploadAttachment(file: File, signal?: AbortSignal): Promise<Attachment> {
  const generation = sessionGeneration;
  if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError');
  if (!state.ready) await initializeAssistant();
  if (!session || !state.ready)
    throw new Error("The assistant server is unavailable.");
  assertCurrent(generation);
  const owner = session;
  if (
    state.running ||
    (state.pending &&
      !(
        state.pending.kind === "question" &&
        state.pending.arguments.fields?.some((f) => f.type === "photo")
      ))
  )
    throw new Error("Finish the current request first.");
  if (file.size > 5 * 1024 * 1024)
    throw new Error("Choose a file smaller than 5 MB.");
  const content = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () =>
      reject(new Error("This file could not be read. Please choose it again."));
    if (signal?.aborted) { reject(new DOMException('Upload cancelled', 'AbortError')); return; }
    const abort = () => { reader.abort(); reject(new DOMException('Upload cancelled', 'AbortError')); };
    signal?.addEventListener('abort', abort, { once: true });
    reader.onloadend = () => signal?.removeEventListener('abort', abort);
    reader.readAsDataURL(file);
  });
  assertCurrent(generation, owner);
  if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError');
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', abort, { once: true });
  const timeout = setTimeout(() => controller.abort('timeout'), 15000);
  let attachment: Attachment;
  try { attachment = await (
    await request(`/sessions/${owner.id}/attachments-json`, {
      method: "POST",
      body: JSON.stringify({ filename: file.name.slice(0, 120), content }),
      signal: controller.signal,
    })
  ).json();
  } finally { clearTimeout(timeout); signal?.removeEventListener('abort', abort); }
  assertCurrent(generation, owner);
  if (signal?.aborted) throw new DOMException('Upload cancelled', 'AbortError');
  update({ attachments: [attachment, ...state.attachments] });
  return attachment;
}
export async function downloadArtifact(artifact: Artifact) {
  if (!session) return;
  const generation = sessionGeneration, owner = session;
  const response = await request(
    `/sessions/${session.id}/files/${artifact.file_id}`,
  );
  const blob = await response.blob();
  assertCurrent(generation, owner);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = artifact.filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 10000);
}
export function useAssistant() {
  const snapshot = useSyncExternalStore(
    (fn) => {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
    () => state,
  );
  useEffect(() => {
    void initializeAssistant();
  }, []);
  return snapshot;
}

export async function changeTask(
  task: FarmTask,
  action: "edit" | "delete" | "restore",
) {
  if (!session || !state.ready)
    throw new Error("The workspace is unavailable.");
  if (state.running) throw new Error("Finish the current request first.");
  const generation = sessionGeneration, owner = session;
  const path = `/sessions/${owner.id}/tasks/${task.id}`;
  try {
    await request(action === "restore" ? path + "/restore" : path, {
      method:
        action === "edit" ? "PATCH" : action === "delete" ? "DELETE" : "POST",
      ...(action === "edit"
        ? {
            body: JSON.stringify({
              title: task.title,
              due_date: task.due_date,
              notes: task.notes ?? "",
              completed: task.completed,
              ...(task.row_version !== undefined ? { row_version: task.row_version } : {}),
            }),
          }
        : task.row_version !== undefined ? { headers: { "If-Match": String(task.row_version) } } : {}),
    });
  } catch (error) {
    assertCurrent(generation, owner);
    if (error instanceof Error && error.message.includes("changed elsewhere")) await sync();
    throw error;
  }
  assertCurrent(generation, owner);
  await sync();
}

export async function inspectWorkspaceTool<T = Record<string, unknown>>(
  tool:
    | "market_prices"
    | "market_trend"
    | "scheme_search"
    | "diagnose_crop"
    | "list_expenses",
  arguments_: Record<string, unknown>,
): Promise<T> {
  const generation = sessionGeneration;
  if (!state.ready) await initializeAssistant();
  if (!session || !state.ready)
    throw new Error("The workspace is unavailable.");
  assertCurrent(generation);
  const owner = session;
  const fetchResult = async () => (await (
    await request(`/sessions/${session.id}/inspect/${tool}`, {
      method: "POST",
      body: JSON.stringify(arguments_),
      signal: AbortSignal.timeout(tool === "diagnose_crop" ? 95000 : 25000),
    })
  ).json()) as T;
  const result = await (["market_prices", "market_trend", "scheme_search"].includes(tool)
    ? workspaceReadCache.read<T>(`${generation}:${owner.id}`, tool, arguments_, fetchResult)
    : fetchResult());
  assertCurrent(generation, owner);
  return result;
}


export function warmWorkspaceReads(): void {
  if (typeof document === "undefined" || document.visibilityState === "hidden" || !navigator.onLine) return;
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
  if (connection?.saveData || /(^|-)2g$/.test(connection?.effectiveType || "")) return;
  void inspectWorkspaceTool("market_prices", { commodity: "Wheat", state: "", observed_only: reportedMarketsOnly })
    .then(() => inspectWorkspaceTool("market_trend", { commodity: "Wheat", state: "", observed_only: reportedMarketsOnly }))
    .catch(() => {});
  void inspectWorkspaceTool("scheme_search", { query: "", state: "" }).catch(() => {});
}


export async function assistantAuthHeaders(): Promise<Record<string, string>> {
  const generation = sessionGeneration;
  await initializeAssistant();
  assertCurrent(generation);
  if (!session || !state.ready) throw new Error(state.error || "Your farm workspace could not connect. Please retry.");
  return { Authorization: `Bearer ${session.token}`, "X-Assistant-Session": session.id };
}

export function getAssistantSessionId(): string | null { return session?.id ?? null; }

export function clearAssistantSession(): void {
  sessionGeneration++;
  invalidateWorkspaceCaches("session");
  controller?.abort("user");
  controller = null;
  initializing = null;
  session = null;
  clearOfflineData();
  try { localStorage.removeItem(key);
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const name = localStorage.key(i);
    if (name?.startsWith("skyview_cache_") || name?.startsWith("skyview_v3_cache_") || name?.startsWith("saved_user_otp_") || name?.startsWith("user_")) localStorage.removeItem(name);
  }
  } catch {                                                                             }
  update({ ready: false, loading: false, running: false, messages: [], pending: null, tasks: [], deletedTasks: [], artifacts: [], attachments: [], conversations: [], catalog: { skills: [], tools: [] }, error: null, status: "" });
}


export async function adoptAssistantSession(id: string, token: string): Promise<void> {
  if (!/^[a-f0-9]{32}$/.test(id) || !token) throw new Error("Invalid workspace capability.");
  clearAssistantSession();
  session = { id, token };
  const generation = sessionGeneration, owner = session;
  try { localStorage.setItem(key, JSON.stringify(session)); } catch {                                      }
  await initializeAssistant();
  assertCurrent(generation, owner);
  if (!state.ready) throw new Error(state.error || "Your workspace could not initialize.");
}


export async function revokeAssistantSession(): Promise<void> {
  let active = session;
  if (!active) {
    try {
      const stored = JSON.parse(localStorage.getItem(key) || "null");
      if (typeof stored?.id === "string" && /^[a-f0-9]{32}$/.test(stored.id) && typeof stored.token === "string") active = stored;
    } catch {                                                     }
  }
  let pending: Promise<Response | void>;
  try {
    pending = active ? fetch(`${base}/api/assistant/sessions/${active.id}/revoke`, { method: "POST", headers: { Authorization: `Bearer ${active.token}`, "X-Assistant-Session": active.id }, signal: AbortSignal.timeout(2500), keepalive: true }) : Promise.resolve();
  } catch {
    clearAssistantSession();
    return;
  }
  clearAssistantSession();
  try { await pending; } catch {                                                                       }
}


export async function rewriteAssistantAnswer(messageId: string): Promise<string> {
  if (!session || state.running || state.pending) throw new Error("Finish the current request before rewriting an answer.");
  if (!navigator.onLine) throw new Error("Reconnect to rewrite this answer. Your original stays here.");
  const owner = session, generation = sessionGeneration;
  const response = await request(`/sessions/${owner.id}/answers/${encodeURIComponent(messageId)}/rewrite`, { method: "POST", signal: AbortSignal.timeout(50000) });
  const body = await response.json(); assertCurrent(generation, owner);
  if (typeof body.text !== "string" || !body.text) throw new Error("No alternative explanation arrived.");
  return body.text;
}
