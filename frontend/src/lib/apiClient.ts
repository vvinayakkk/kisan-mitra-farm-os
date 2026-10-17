import { assistantAuthHeaders, getAssistantSessionId } from "./assistantClient";
import { cacheableRead, readSnapshot, saveSnapshot } from "./offlineStore";
import { invalidateWorkspaceCaches, onWorkspaceCacheInvalidated } from "./workspaceCacheLifecycle";


const responses = new Map<string, { body: string; headers: [string, string][]; status: number; expires: number }>();
const pending = new Map<string, Promise<Response>>();
const requests = new Set<AbortController>();
let cacheEpoch = 0;
const READ_TTL = 15_000;
const CACHE_CAPACITY = 48;
const READ_PATHS = /^\/api\/(?:profile(?:$|\?)|farms(?:$|\?)|plots(?:$|\?)|mandi(?:\/|$|\?)|sensors\/|marketplace\/(?:farmers|pooling)(?:$|\?)|farm-workspace\/|onboarding\/(?:options|starter-plans)(?:$|\?))/;
onWorkspaceCacheInvalidated(reason => {
  cacheEpoch++;
  responses.clear();
  pending.clear();
  if (reason === "session") { requests.forEach(request => request.abort()); requests.clear(); }
});
function requestPath(url: string): string {
  try { const parsed = new URL(url, "http://workspace.local"); return parsed.pathname + parsed.search; }
  catch { return url; }
}



function waitForConsumer<T>(result: Promise<T>, signal?: AbortSignal | null): Promise<T> {
  if (!signal) return result;
  return new Promise<T>((resolve, reject) => {
    const cancelled = () => { signal.removeEventListener("abort", cancelled); reject(new DOMException("Request cancelled", "AbortError")); };


    result.then(value => { signal.removeEventListener("abort", cancelled); resolve(value); }, error => { signal.removeEventListener("abort", cancelled); reject(error); });
    if (signal.aborted) cancelled();
    else signal.addEventListener("abort", cancelled, {once: true});
  });
}


export async function apiFetch(input: RequestInfo | URL, options: RequestInit = {}): Promise<Response> {
  const auth = await assistantAuthHeaders();
  const callerSignal = options.signal ?? (input instanceof Request ? input.signal : undefined);
  if (callerSignal?.aborted) throw new DOMException("Request cancelled", "AbortError");
  const owner = auth["X-Assistant-Session"] || getAssistantSessionId();
  if (getAssistantSessionId() !== owner) throw new Error("Your farm session changed. Please reopen this page.");
  const headers = new Headers(input instanceof Request ? input.headers : undefined);
  new Headers(options.headers).forEach((value, key) => headers.set(key, value));
  Object.entries(auth).forEach(([key, value]) => headers.set(key, value));
  const url = input instanceof Request ? input.url : String(input);
  const method = (options.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
  const read = method === "GET" && cacheableRead(url);
  const path = requestPath(url);
  const canCache = method === "GET" && READ_PATHS.test(path) && options.cache !== "no-store" && options.cache !== "reload";
  const cacheKey = JSON.stringify([owner, url, headers.get("Accept-Language")]);
  const epoch = cacheEpoch;
  const cached = canCache ? responses.get(cacheKey) : undefined;
  if (cached && cached.expires > Date.now()) {
    responses.delete(cacheKey); responses.set(cacheKey, cached);
    return new Response(cached.body, { status: cached.status, headers: cached.headers });
  }
  if (cached) responses.delete(cacheKey);
  const existing = canCache ? pending.get(cacheKey) : undefined;
  if (existing) return (await waitForConsumer(existing, callerSignal)).clone();
  const controller = canCache || !callerSignal ? new AbortController() : null;
  if (controller) requests.add(controller);
  const execute = async (): Promise<Response> => {
    try {
      const response = await fetch(input, { ...options, headers, signal: canCache ? controller!.signal : callerSignal ?? controller?.signal });
      if (getAssistantSessionId() !== owner) throw new Error("Your farm session changed. Please reopen this page.");
      if (response.ok && read && owner) {
        const clone = response.clone();
        void clone.text().then(body => { if (getAssistantSessionId() === owner) saveSnapshot(owner, url, body); }).catch(() => {});
      }
      if (response.ok && method !== "GET" && method !== "HEAD" && !/\/marketplace\/(?:match|circular-barter)$/.test(path)) invalidateWorkspaceCaches();
      if (canCache && response.ok && response.headers.get("Content-Type")?.includes("application/json")) {
        const body = await response.clone().text();
        if (getAssistantSessionId() !== owner) throw new Error("Your farm session changed. Please reopen this page.");
        if (epoch === cacheEpoch && body.length <= 512_000) {
          const responseHeaders: [string, string][] = [];
          response.headers.forEach((value, key) => responseHeaders.push([key, value]));
          responses.set(cacheKey, { body, headers: responseHeaders, status: response.status, expires: Date.now() + READ_TTL });
          while (responses.size > CACHE_CAPACITY) responses.delete(responses.keys().next().value!);
        }
      }
      return response;
    } catch (error) {
      if (!(canCache ? controller?.signal.aborted : callerSignal?.aborted) && getAssistantSessionId() === owner && read && owner && error instanceof TypeError) {
        const snapshot = readSnapshot(owner, url);
        if (snapshot) return snapshot;
      }
      throw error;
    } finally {
      if (controller) requests.delete(controller);
    }
  };
  const result = execute();
  if (!canCache) return result;
  pending.set(cacheKey, result);

  const settled = () => { if (pending.get(cacheKey) === result) pending.delete(cacheKey); };
  void result.then(settled, settled);
  return (await waitForConsumer(result, callerSignal)).clone();
}
