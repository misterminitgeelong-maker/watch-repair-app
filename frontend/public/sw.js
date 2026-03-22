/* Mainspring PWA Service Worker - caches app shell for offline viewing */
const CACHE_NAME = 'mainspring-v1'

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(() => self.skipWaiting()))
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return
  const url = new URL(e.request.url)
  const isApi = url.pathname.startsWith('/v1/')
  if (isApi) return
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok && url.origin === location.origin) {
          const clone = res.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone))
        }
        return res
      })
      .catch(() =>
        caches.match(e.request).then((cached) => cached || caches.match('/index.html').then((r) => r || new Response('Offline', { status: 503 })))
      )
  )
})
