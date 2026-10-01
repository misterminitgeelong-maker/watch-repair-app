import { beforeAll, afterAll, beforeEach, describe, expect, it } from 'vitest'
import { http, HttpResponse, delay } from 'msw'
import { testServer } from '@/test/msw/server'
import api, { clearStoredTokens, getStoredAccessToken, getStoredRefreshToken, refreshAuth, setStoredTokens } from './client'

const base = api.defaults.baseURL
beforeAll(() => { api.defaults.baseURL = 'http://127.0.0.1/v1' })
afterAll(() => { api.defaults.baseURL = base })
beforeEach(() => { clearStoredTokens(); setStoredTokens('expired-access', 'refresh-old') })

function protectedResource() {
  testServer.use(http.get('*/v1/protected', ({ request }) => {
    return request.headers.get('Authorization') === 'Bearer fresh-access'
      ? HttpResponse.json({ ok: true }) : new HttpResponse(null, { status: 401 })
  }))
}

describe('deployment-safe session refresh', () => {
  it('rejects an invalid refresh without recursing or hanging waiting requests', async () => {
    protectedResource()
    let calls = 0
    testServer.use(http.post('*/v1/auth/refresh', () => { calls++; return new HttpResponse(null, { status: 401 }) }))
    const results = await Promise.allSettled([api.get('/protected'), api.get('/protected')])
    expect(results.every(result => result.status === 'rejected')).toBe(true)
    expect(calls).toBe(1)
    expect(getStoredAccessToken()).toBeNull()
  }, 1500)

  it('shares refresh across simultaneous reactive and proactive callers', async () => {
    protectedResource()
    let calls = 0
    testServer.use(http.post('*/v1/auth/refresh', async () => {
      calls++; await delay(40)
      return HttpResponse.json({ access_token: 'fresh-access', refresh_token: 'refresh-new', token_type: 'bearer' })
    }))
    const results = await Promise.all([api.get('/protected'), api.get('/protected'), refreshAuth('refresh-old')])
    expect(results[0].data.ok).toBe(true)
    expect(results[1].data.ok).toBe(true)
    expect(calls).toBe(1)
    expect(getStoredRefreshToken()).toBe('refresh-new')
  })

  it('retains login through a 503 and recovers on the next request', async () => {
    protectedResource()
    testServer.use(http.post('*/v1/auth/refresh', () => new HttpResponse(null, { status: 503 })))
    await expect(api.get('/protected')).rejects.toMatchObject({ response: { status: 503 } })
    expect(getStoredAccessToken()).toBe('expired-access')
    expect(getStoredRefreshToken()).toBe('refresh-old')
    testServer.use(http.post('*/v1/auth/refresh', () => HttpResponse.json({ access_token: 'fresh-access', refresh_token: 'refresh-new' })))
    await expect(api.get('/protected')).resolves.toMatchObject({ data: { ok: true } })
  })

  it('retains login when refresh loses its network connection', async () => {
    testServer.use(http.post('*/v1/auth/refresh', () => HttpResponse.error()))
    await expect(refreshAuth('refresh-old')).rejects.toBeDefined()
    expect(getStoredAccessToken()).toBe('expired-access')
  })

  it('cannot resurrect a logged-out session from an in-flight refresh', async () => {
    let release!: () => void
    let started!: () => void
    const ready = new Promise<void>(resolve => { started = resolve })
    testServer.use(http.post('*/v1/auth/refresh', async () => {
      started(); await new Promise<void>(resolve => { release = resolve })
      return HttpResponse.json({ access_token: 'fresh-access', refresh_token: 'refresh-new' })
    }))
    const pending = refreshAuth('refresh-old')
    const rejected = expect(pending).rejects.toMatchObject({ code: 'ERR_CANCELED' })
    await ready; clearStoredTokens(); release()
    await rejected
    expect(getStoredAccessToken()).toBeNull()
  })

  it('does not clear a new login when an older refresh is rejected', async () => {
    let release!: () => void
    let started!: () => void
    const ready = new Promise<void>(resolve => { started = resolve })
    testServer.use(http.post('*/v1/auth/refresh', async () => {
      started(); await new Promise<void>(resolve => { release = resolve })
      return new HttpResponse(null, { status: 401 })
    }))
    const pending = refreshAuth('refresh-old')
    const rejected = expect(pending).rejects.toBeDefined()
    await ready; setStoredTokens('another-login', 'another-refresh'); release()
    await rejected
    expect(getStoredAccessToken()).toBe('another-login')
  })

  it('cannot overwrite a login changed by another browser tab', async () => {
    let started!: () => void
    let release!: () => void
    const ready = new Promise<void>(resolve => { started = resolve })
    testServer.use(http.post('*/v1/auth/refresh', async () => {
      started(); await new Promise<void>(resolve => { release = resolve })
      return HttpResponse.json({ access_token: 'fresh-access', refresh_token: 'refresh-new' })
    }))
    const pending = refreshAuth('refresh-old')
    const rejected = expect(pending).rejects.toMatchObject({ code: 'ERR_CANCELED' })
    await ready
    // A storage write in a different tab doesn't call this module's setter.
    sessionStorage.setItem('token', 'other-tab-login')
    sessionStorage.setItem('refresh_token', 'other-tab-refresh')
    release()
    await rejected
    expect(getStoredAccessToken()).toBe('other-tab-login')
  })

  it('does not replay an old account request under a new login', async () => {
    let started!: () => void
    let release!: () => void
    const ready = new Promise<void>(resolve => { started = resolve })
    let calls = 0
    testServer.use(http.post('*/v1/account-change', async () => {
      calls++; started(); await new Promise<void>(resolve => { release = resolve })
      return new HttpResponse(null, { status: 401 })
    }))
    const pending = api.post('/account-change', { value: 'belongs to old user' })
    const rejected = expect(pending).rejects.toMatchObject({ code: 'ERR_CANCELED' })
    await ready; setStoredTokens('another-login', 'another-refresh'); release()
    await rejected
    expect(calls).toBe(1)
    expect(getStoredAccessToken()).toBe('another-login')
  })

  it('a bad login does not enter the refresh interceptor', async () => {
    testServer.use(http.post('*/v1/auth/login', () => new HttpResponse(null, { status: 401 })))
    await expect(api.post('/auth/login', {})).rejects.toMatchObject({ response: { status: 401 } })
    expect(getStoredAccessToken()).toBe('expired-access')
  })

  it('does not replay a mutation after a server failure', async () => {
    let calls = 0
    testServer.use(http.post('*/v1/payment', () => { calls++; return new HttpResponse(null, { status: 503 }) }))
    await expect(api.post('/payment', { amount: 100 })).rejects.toBeDefined()
    expect(calls).toBe(1)
  })
})
