// AgriMarket Service Worker v3
const CACHE_APP   = 'agrimarket-app-v3';
const CACHE_TILES = 'agrimarket-tiles-v1';

const APP_SHELL = [
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/offline',
];

// ── Install ──────────────────────────────────────────────
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_APP)
      .then(c => c.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

// ── Activate ─────────────────────────────────────────────
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_APP && k !== CACHE_TILES)
            .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ────────────────────────────────────────────────
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Skip non-GET and cross-origin API calls (SMS, etc.)
  if (e.request.method !== 'GET') return;
  if (!url.origin.includes(self.location.origin) &&
      !url.hostname.includes('tile.openstreetmap.org')) return;

  // Map tiles — cache first
  if (url.hostname.includes('tile.openstreetmap.org')) {
    e.respondWith(
      caches.open(CACHE_TILES).then(cache =>
        cache.match(e.request).then(cached => {
          if (cached) return cached;
          return fetch(e.request).then(res => {
            if (res.ok) cache.put(e.request, res.clone());
            return res;
          }).catch(() => cached || new Response('', {status: 503}));
        })
      )
    );
    return;
  }

  // Static assets — cache first, then network
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(res => {
          if (res.ok) {
            caches.open(CACHE_APP).then(c => c.put(e.request, res.clone()));
          }
          return res;
        });
      })
    );
    return;
  }

  // App pages — network first, fall back to cache, then offline page
  e.respondWith(
    fetch(e.request)
      .then(res => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(CACHE_APP).then(c => c.put(e.request, clone));
        }
        return res;
      })
      .catch(() =>
        caches.match(e.request).then(cached =>
          cached || caches.match('/offline')
        )
      )
  );
});
