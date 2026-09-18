/**
 * Mainspring PWA — cache app shell for install + offline; bust caches by bumping CACHE_VERSION.
 * Static assets: cache-first. API /v1/*: network-first (no JSON cache). Navigation: network, then shell, then offline page.
 */
// Bump when shell assets (index, offline, icons, manifest) change so deploys replace old caches.
const CACHE_VERSION = 'mainspring-app-v11-pwa-install'
const STATIC_CACHE = `mainspring-static-${CACHE_VERSION}`

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/offline.html',
  '/icon-192.png',
  '/icon-512.png',
  '/icon-maskable-192.png',
  '/icon-maskable-512.png',
  '/apple-touch-icon.png',
  '/favicon.svg',
  '/mainspring-logo.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      // addAll is all-or-nothing: one 404 would leave the shell uncached, so
      // each URL is cached independently and failures are tolerated.
      .then((cache) => Promise.all(PRECACHE_URLS.map((url) => cache.add(url).catch(() => undefined))))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k.startsWith('mainspring-') && k !== STATIC_CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  )
})

// Lets the page ask a waiting worker to take over instead of waiting for all
// tabs to close (the page decides when; this only obeys).
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') self.skipWaiting()
})

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return

  const url = new URL(event.request.url)
  if (url.origin !== self.location.origin) return

  // Range requests (media seeking) must not be served from the cache.
  if (event.request.headers.has('range')) return

  // API: network-first; never cache JSON API responses here (fresh data when online).
  if (url.pathname.startsWith('/v1/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: 'You are offline. Connect to load or refresh data.' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' },
          })
        )
      )
    )
    return
  }

  // HTML navigations: try network, then cached SPA shell, then offline page.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone()
            caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, copy))
          }
          return res
        })
        .catch(async () => {
          // The SPA shell boots the app, which can serve cached screens; the
          // static offline page is the last resort.
          const shell = (await caches.match('/index.html')) || (await caches.match('/'))
          if (shell) return shell
          const offline = await caches.match('/offline.html')
          return (
            offline ||
            new Response('Offline', {
              status: 503,
              statusText: 'Offline',
              headers: { 'Content-Type': 'text/plain' },
            })
          )
        })
    )
    return
  }

  // Hashed Vite bundles: network-first so deploys replace stale JS without waiting for SW version bump.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone()
            caches.open(STATIC_CACHE).then((cache) => cache.put(event.request, copy))
          }
          return res
        })
        // respondWith rejects on undefined, so always resolve to a Response.
        .catch(async () => {
          const cached = await caches.match(event.request)
          return (
            cached ||
            new Response('', { status: 504, statusText: 'Offline', headers: { 'Content-Type': 'text/plain' } })
          )
        })
    )
    return
  }

  // Static (JS/CSS/assets, images): cache-first, then network and update cache.
  event.respondWith(
    caches.open(STATIC_CACHE).then((cache) =>
      cache.match(event.request).then((cached) => {
        if (cached) return cached
        return fetch(event.request)
          .then((res) => {
            if (res.ok && res.type === 'basic') {
              cache.put(event.request, res.clone())
            }
            return res
          })
          .catch(async () => {
            const fallback = await caches.match(event.request)
            if (fallback) return fallback
            throw new Error('offline')
          })
      })
    )
  )
})
