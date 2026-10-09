/**
 * Storage for an HQ "open shop" support session (see hqEnterShop.tsx).
 *
 * The HQ login is parked in sessionStorage while the short shop-owner session
 * runs. It lives here, away from the React code, so the API client can unwind
 * the session when the shop token expires and logout can discard what is left.
 */
export const HQ_PREV_TOKEN_KEY = 'hq_prev_token'
export const HQ_PREV_REFRESH_KEY = 'hq_prev_refresh_token'
export const HQ_SESSION_EXPIRES_KEY = 'hq_enter_shop_expires_at'
export const HQ_SESSION_SHOP_KEY = 'hq_enter_shop_name'
export const HQ_RETURN_PATH_KEY = 'hq_enter_shop_return_path'

export const DEFAULT_HQ_RETURN_PATH = '/minit/accounts'

export interface ParkedHqSession {
  access: string
  refresh: string | null
  returnPath: string
}

export function readParkedHqSession(): ParkedHqSession | null {
  try {
    const access = sessionStorage.getItem(HQ_PREV_TOKEN_KEY)
    if (!access) return null
    return {
      access,
      refresh: sessionStorage.getItem(HQ_PREV_REFRESH_KEY) || null,
      returnPath: sessionStorage.getItem(HQ_RETURN_PATH_KEY) || DEFAULT_HQ_RETURN_PATH,
    }
  } catch {
    return null
  }
}

/** Forget the parked HQ login and the support-session banner state. */
export function clearHqSupportSession(): void {
  try {
    for (const key of [HQ_PREV_TOKEN_KEY, HQ_PREV_REFRESH_KEY, HQ_SESSION_EXPIRES_KEY, HQ_SESSION_SHOP_KEY, HQ_RETURN_PATH_KEY]) {
      sessionStorage.removeItem(key)
    }
  } catch {
    /* ignore storage restrictions */
  }
}
