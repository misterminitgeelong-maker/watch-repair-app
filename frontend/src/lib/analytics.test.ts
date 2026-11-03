import { afterEach, describe, expect, it } from 'vitest'
import { initAnalytics } from './analytics'

afterEach(() => {
  document.head.innerHTML = ''
})

describe('initAnalytics', () => {
  it('does nothing when no domain is configured', () => {
    expect(initAnalytics({})).toBe(false)
    expect(document.querySelector('script[data-plausible]')).toBeNull()
  })

  it('does nothing in the native app', () => {
    expect(initAnalytics({ domain: 'mainspring.au' }, true)).toBe(false)
  })

  it('injects the Plausible script once', () => {
    expect(initAnalytics({ domain: 'mainspring.au' })).toBe(true)
    expect(initAnalytics({ domain: 'mainspring.au' })).toBe(true)
    const scripts = document.querySelectorAll('script[data-plausible]')
    expect(scripts).toHaveLength(1)
    expect((scripts[0] as HTMLScriptElement).src).toBe('https://plausible.io/js/script.js')
    expect((scripts[0] as HTMLScriptElement).dataset.domain).toBe('mainspring.au')
  })

  it('supports a self-hosted origin', () => {
    initAnalytics({ domain: 'mainspring.au', host: 'https://stats.example.com/' })
    expect((document.querySelector('script[data-plausible]') as HTMLScriptElement).src).toBe(
      'https://stats.example.com/js/script.js',
    )
  })
})
