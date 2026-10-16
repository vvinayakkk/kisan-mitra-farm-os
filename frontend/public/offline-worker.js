const CACHE = "skyview-shell-v2";
const SHELL = ["/", "/manifest.webmanifest", "/farm-icon.svg"];
const ASSET = /^\/assets\/[A-Za-z0-9_./-]+\.(?:js|css|woff2?|svg|png)$/;
const PRIVATE = /^\/(?:api|admin|webhook|health|docs|openapi\.json)(?:\/|$)/;

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(SHELL);


    const index = await cache.match("/");
    if (!index) throw new Error("The offline shell was not saved.");
    const html = await index.text();
    const assets = new Set();
    for (const match of html.matchAll(/(?:src|href)\s*=\s*["']([^"']+)["']/g)) {
      const url = new URL(match[1], self.location.origin);
      if (url.origin === self.location.origin && !url.search && ASSET.test(url.pathname)) assets.add(url.pathname);
    }

    const manifest = await fetch('/offline-assets.json', { credentials: 'omit', cache: 'no-store' });
    if (!manifest.ok) throw new Error('The offline bundle manifest is unavailable.');
    const bundle = await manifest.json();
    if (!Array.isArray(bundle.assets) || bundle.assets.length > 1000) throw new Error('The offline bundle manifest is invalid.');
    for (const item of bundle.assets) {
      if (typeof item !== 'string') throw new Error('The offline bundle path is invalid.');
      const url = new URL(item, self.location.origin);
      if (url.origin !== self.location.origin || url.search || url.hash || !ASSET.test(url.pathname)) throw new Error('The offline bundle must contain public static assets only.');
      assets.add(url.pathname);
    }
    if (assets.size) await cache.addAll([...assets]);
  })());
});
self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith("skyview-shell-") && key !== CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener("fetch", event => {
  const request = event.request, url = new URL(request.url);
  let path;
  try { path = decodeURIComponent(url.pathname); } catch { return; }
  if (request.method !== "GET" || url.origin !== self.location.origin || request.headers.has("Authorization") || request.headers.has("X-Assistant-Session") || PRIVATE.test(path)) return;
  if (request.mode === "navigate") {


    event.respondWith(fetch(request).catch(async () => (await caches.open(CACHE)).match("/") || Response.error()));
  } else if (!url.search && ASSET.test(url.pathname)) {
    event.respondWith(caches.open(CACHE).then(async cache => {
      const saved = await cache.match(request);
      if (saved) return saved;
      const response = await fetch(request);
      if (response.ok && response.type !== "opaque") await cache.put(request, response.clone());
      return response;
    }));
  }
});
