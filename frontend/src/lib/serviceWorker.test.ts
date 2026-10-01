import { describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source = readFileSync('public/sw.js', 'utf8')
const origin = 'https://app.test'

function worker() {
  const listeners: Record<string, (event: unknown) => void> = {}
  const stores = new Map<string, Map<string, Response>>()
  const keyOf = (request: string | Request) => typeof request === 'string' ? new URL(request, origin).href : request.url
  const caches = {
    keys: async () => [...stores.keys()],
    delete: vi.fn(async (key: string) => stores.delete(key)),
    open: async (name: string) => {
      const store = stores.get(name) ?? new Map<string, Response>()
      stores.set(name, store)
      return {
        keys: async () => [...store.keys()].map(url => new Request(url)),
        match: async (request: string | Request) => store.get(keyOf(request))?.clone(),
        put: async (request: string | Request, response: Response) => { store.set(keyOf(request), response.clone()) },
        add: async () => {},
      }
    },
  }
  const fetch = vi.fn(async () => new Response('missing', { status: 404 }))
  const self = { location: { origin }, clients: { claim: vi.fn() }, skipWaiting: vi.fn(), addEventListener: (type: string, handler: (event: unknown) => void) => { listeners[type] = handler } }
  runInNewContext(source, { self, caches, fetch, URL, Response })
  return { caches, fetch, listeners }
}

describe('service worker deployment continuity', () => {
  it('retains immutable bundles while migrating and replacing the shell cache', async () => {
    const { caches, listeners } = worker()
    const old = await caches.open('mainspring-static-old')
    await old.put('/assets/OldPage-abcdefgh.js', new Response('old route'))
    await old.put('/index.html', new Response('old shell'))
    let activation!: Promise<unknown>
    listeners.activate({ waitUntil: (promise: Promise<unknown>) => { activation = promise } })
    await activation
    expect(caches.delete).toHaveBeenCalledWith('mainspring-static-old')
    const assets = await caches.open('mainspring-assets-v1')
    expect(await (await assets.match('/assets/OldPage-abcdefgh.js'))?.text()).toBe('old route')
    expect(await assets.match('/index.html')).toBeUndefined()
  })

  it('loads an old cached bundle without asking a new server that would return 404', async () => {
    const { caches, fetch, listeners } = worker()
    const cache = await caches.open('mainspring-assets-v1')
    await cache.put('/assets/OldPage-abcdefgh.js', new Response('old route'))
    let response!: Promise<Response>
    listeners.fetch({ request: new Request(origin + '/assets/OldPage-abcdefgh.js'), respondWith: (promise: Promise<Response>) => { response = promise } })
    expect(await (await response).text()).toBe('old route')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('never puts API data into the build cache', async () => {
    const { caches, fetch, listeners } = worker()
    fetch.mockResolvedValue(new Response('{}'))
    let response!: Promise<Response>
    listeners.fetch({ request: new Request(origin + '/v1/auth/session'), respondWith: (promise: Promise<Response>) => { response = promise } })
    await response
    expect(await caches.keys()).toEqual([])
  })
})
