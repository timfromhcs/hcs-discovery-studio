/*
 * Service worker for the offline path.
 *
 * Deliberately small and dependency-free (no Workbox, no new lockfile entries):
 *
 * - navigations are network-first, so a deployment is picked up immediately and an
 *   offline reload falls back to the cached shell;
 * - same-origin static assets are cache-first (the built files are content-hashed,
 *   so a cached copy can never be stale);
 * - `/api/` is never cached: stale API data would be a silent lie, and the offline
 *   lab does not need it;
 * - the cache name carries a version, and activation deletes every other cache.
 *
 * The RDKit WebAssembly module (~7 MB) is cached on first use, which is what makes
 * the offline lab usable without a network after the first visit.
 */

const VERSION = "hcs-shell-v1";
const SHELL = ["/", "/index.html", "/favicon.svg", "/manifest.webmanifest"];


self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

async function networkFirstNavigation(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cache = await caches.open(VERSION);
    return (
      (await cache.match(request, { ignoreVary: true })) ??
      (await cache.match("/index.html", { ignoreVary: true })) ??
      Response.error()
    );
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(VERSION);
  // ignoreVary: the shell and the hashed assets are immutable, and matching on
  // Vary headers made a warm-up fetch (different Accept/Origin headers) miss the
  // entry that this request should have hit.
  const cached = await cache.match(request, { ignoreVary: true });
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok && response.type === "basic") {
    cache.put(request, response.clone());
  }
  return response;
}

/**
 * Warm the cache with the URLs that booted this page.
 *
 * A service worker only controls the page after activation, so the scripts and
 * stylesheets of the very first visit bypass it. Without this message a user who
 * loads the page once and then goes offline gets cached HTML pointing at JS that was
 * never stored. The page posts its own resource URLs; the worker stores what it can
 * and ignores the rest.
 */
async function cacheUrls(urls) {
  const cache = await caches.open(VERSION);
  await Promise.all(
    urls.map((url) => cache.add(url).catch(() => undefined)),
  );
}

self.addEventListener("message", (event) => {
  const data = event.data;
  if (!data || data.type !== "CACHE_URLS" || !Array.isArray(data.urls)) return;
  const urls = data.urls.filter((url) => typeof url === "string").slice(0, 64);
  event.waitUntil(cacheUrls(urls));
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // never cache API responses
  
  if (request.mode === "navigate") {
    event.respondWith(networkFirstNavigation(request));
    return;
  }
  event.respondWith(cacheFirst(request));
});


