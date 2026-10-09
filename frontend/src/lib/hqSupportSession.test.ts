import { describe, expect, it, beforeEach } from 'vitest'
import { clearStoredTokens } from '@/lib/api/client'
import { HQ_PREV_REFRESH_KEY, HQ_PREV_TOKEN_KEY, HQ_SESSION_SHOP_KEY, readParkedHqSession } from '@/lib/hqSupportSession'

describe('HQ support session storage', () => {
  beforeEach(() => sessionStorage.clear())

  it('reads the parked HQ login with a default return path', () => {
    sessionStorage.setItem(HQ_PREV_TOKEN_KEY, 'hq-access')
    sessionStorage.setItem(HQ_PREV_REFRESH_KEY, 'hq-refresh')
    expect(readParkedHqSession()).toEqual({ access: 'hq-access', refresh: 'hq-refresh', returnPath: '/minit/accounts' })
  })

  it('is cleared with the tokens, so a logout does not leave the banner behind', () => {
    sessionStorage.setItem(HQ_PREV_TOKEN_KEY, 'hq-access')
    sessionStorage.setItem(HQ_SESSION_SHOP_KEY, 'Some Shop')
    clearStoredTokens()
    expect(readParkedHqSession()).toBeNull()
    expect(sessionStorage.getItem(HQ_SESSION_SHOP_KEY)).toBeNull()
  })
})
