import { afterEach, describe, expect, it } from 'vitest'
import { initAnalytics } from './analytics'

afterEach(() => {
  document.head.innerHTML = ''
})

describe('initAnalytics', () => {
  it('does nothing when no token is configured', () => {
    expect(initAnalytics({})).toBe(false)
    expect(document.querySelector('script[data-cf-beacon]')).toBeNull()
  })

  it('does nothing in the native app', () => {
    expect(initAnalytics({ token: 'abc' }, true)).toBe(false)
  })

  it('injects the Cloudflare beacon once', () => {
    expect(initAnalytics({ token: 'abc' })).toBe(true)
    expect(initAnalytics({ token: 'abc' })).toBe(true)
    const scripts = document.querySelectorAll('script[data-cf-beacon]')
    expect(scripts).toHaveLength(1)
    expect((scripts[0] as HTMLScriptElement).src).toBe('https://static.cloudflareinsights.com/beacon.min.js')
    expect(JSON.parse(scripts[0].getAttribute('data-cf-beacon')!)).toEqual({ token: 'abc' })
  })
})
