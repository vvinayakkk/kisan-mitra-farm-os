import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { runInNewContext } from 'node:vm';
import { expect, it, vi } from 'vitest';

function worker() {
  const handlers: Record<string, (event: any) => void> = {};
  const cache = {
    addAll: vi.fn().mockResolvedValue(undefined),
    match: vi.fn(async (request: string | Request) => typeof request === 'string' && request === '/' ? new Response('<script type="module" src="/assets/index-abc.js"></script><link href="/assets/index-abc.css" rel="stylesheet"><script src="https://evil.example/assets/foreign.js"></script><script src="/api/profile"></script>') : undefined),
    put: vi.fn().mockResolvedValue(undefined),
  };
  const fetch = vi.fn(async (request: string | Request) => request === '/offline-assets.json' ? Response.json({ assets: ['/assets/index-abc.js', '/assets/index-abc.css', '/assets/Advisor-lazy.js'] }) : Promise.reject(new TypeError('Offline')));
  const caches = { open: vi.fn().mockResolvedValue(cache), keys: vi.fn().mockResolvedValue(['skyview-shell-v1', 'other-app']), delete: vi.fn().mockResolvedValue(true) };
  const claim = vi.fn().mockResolvedValue(undefined);
  runInNewContext(readFileSync(resolve('public/offline-worker.js'), 'utf8'), { self: { location: { origin: 'https://farm.test' }, clients: { claim }, addEventListener: (name: string, handler: (event: any) => void) => { handlers[name] = handler; } }, caches, fetch, URL, Response, Set });
  return { handlers, cache, fetch, caches, claim };
}

it('installs the actual public entry bundles before the first offline reload', async () => {
  const { handlers, cache } = worker();
  let pending: Promise<void> | undefined;
  handlers.install({ waitUntil: (promise: Promise<void>) => { pending = promise; } });
  await pending;
  expect(cache.addAll.mock.calls[0][0]).toEqual(['/', '/manifest.webmanifest', '/farm-icon.svg']);
  expect(cache.addAll.mock.calls[1][0]).toEqual(['/assets/index-abc.js', '/assets/index-abc.css', '/assets/Advisor-lazy.js']);
});
it('only removes this application’s obsolete shell and claims open pages', async () => {
  const { handlers, caches, claim } = worker();
  let pending: Promise<void> | undefined;
  handlers.activate({ waitUntil: (promise: Promise<void>) => { pending = promise; } });
  await pending;
  expect(caches.delete).toHaveBeenCalledWith('skyview-shell-v1');
  expect(caches.delete).not.toHaveBeenCalledWith('other-app');
  expect(claim).toHaveBeenCalledOnce();
});
it('never intercepts authenticated API navigation, capabilities, mutations or external requests', () => {
  const { handlers, fetch, cache } = worker();
  for (const request of [
    { url: 'https://farm.test/api/profile', method: 'GET', mode: 'navigate', headers: new Headers() },
    { url: 'https://farm.test/a%70i/profile', method: 'GET', mode: 'navigate', headers: new Headers() },
    { url: 'https://farm.test/api%2Fprofile', method: 'GET', mode: 'navigate', headers: new Headers() },
    { url: 'https://farm.test/admin/tables', method: 'GET', mode: 'navigate', headers: new Headers() },
    { url: 'https://farm.test/openapi.json', method: 'GET', mode: 'navigate', headers: new Headers() },
    { url: 'https://farm.test/workspace', method: 'GET', mode: 'navigate', headers: new Headers({ Authorization: 'Bearer capability' }) },
    { url: 'https://farm.test/workspace', method: 'GET', mode: 'navigate', headers: new Headers({ 'X-Assistant-Session': 'private-session' }) },
    { url: 'https://farm.test/api/profile', method: 'PUT', mode: 'cors', headers: new Headers() },
    { url: 'https://other.test/assets/main.js', method: 'GET', mode: 'cors', headers: new Headers() },
  ]) {
    const respondWith = vi.fn(); handlers.fetch({ request, respondWith }); expect(respondWith).not.toHaveBeenCalled();
  }
  expect(fetch).not.toHaveBeenCalled(); expect(cache.put).not.toHaveBeenCalled();
});
it('offline navigation receives only the cached public shell', async () => {
  const { handlers, cache } = worker();
  let pending: Promise<Response> | undefined;
  handlers.fetch({ request: { url: 'https://farm.test/workspace?view=chat', method: 'GET', mode: 'navigate', headers: new Headers() }, respondWith: (promise: Promise<Response>) => { pending = promise; } });
  expect(await (await pending)!.text()).toContain('/assets/index-abc.js');
  expect(cache.put).not.toHaveBeenCalled();
});
it('does not cache queried assets or opaque responses', async () => {
  const { handlers, fetch, cache } = worker();
  const respondWith = vi.fn();
  handlers.fetch({ request: { url: 'https://farm.test/assets/main.js?token=private', method: 'GET', mode: 'cors', headers: new Headers() }, respondWith });
  expect(respondWith).not.toHaveBeenCalled();
  fetch.mockResolvedValue({ ok: true, type: 'opaque' } as any);
  let pending: Promise<Response> | undefined;
  handlers.fetch({ request: { url: 'https://farm.test/assets/main.js', method: 'GET', mode: 'cors', headers: new Headers() }, respondWith: (promise: Promise<Response>) => { pending = promise; } });
  await pending;
  expect(cache.put).not.toHaveBeenCalled();
});

it('rejects private or cross-origin entries in the generated bundle manifest', async () => {
  const { handlers, cache, fetch } = worker();
  fetch.mockResolvedValue(Response.json({ assets: ['/api/profile'] }));
  let pending: Promise<void> | undefined;
  handlers.install({ waitUntil: (promise: Promise<void>) => { pending = promise; } });
  await expect(pending).rejects.toThrow('public static assets only');
  expect(cache.addAll).toHaveBeenCalledTimes(1);
});
