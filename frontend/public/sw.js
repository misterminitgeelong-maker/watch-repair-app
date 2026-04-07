/**
 * Mainspring PWA — cache app shell for install + offline; bust caches by bumping CACHE_VERSION.
 * Static assets: cache-first. API /v1/*: network-first (no JSON cache). Navigation: network, then shell, then offline page.
 */
// Bump when shell assets (index, offline, icons, manifest) change so deploys replace old caches.
const CACHE_VERSION = 'mainspring-app-v5'
const STATIC_CACHE = `mainspring-static-${CACHE_VERSION}`

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/offline.html',
  '/icon-192.png',
  '/icon-512.png',
  '/mainspring-logo.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
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

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return

  const url = new URL(event.request.url)
  if (url.origin !== self.location.origin) return

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
          const shell = await caches.match('/index.html')
          if (shell) return shell
          const offline = await caches.match('/offline.html')
          return offline || new Response('Offline', { status: 503, statusText: 'Offline' })
        })
    )
    return
  }

  // Static (JS/CSS/assets, images): cache-first, then network and update cache.
  event.respondWith(
    caches.open(STATIC_CACHE).then((cache) =>
      cache.match(event.request).then((cached) => {
        if (cached) return cached
        return fetch(event.request).then((res) => {
          if (res.ok && res.type === 'basic') {
            cache.put(event.request, res.clone())
          }
          return res
        })
      })
    )
  )
})
