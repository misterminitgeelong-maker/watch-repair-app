/**
 * The Shop ID the login form pre-fills. Separate from the last-login slug hint
 * in minitProduct.ts, which drives branding and is cleared on sign-out: this
 * one has to survive sign-out, because that is exactly when it is needed.
 */
const KEY = 'mainspring.rememberedShopId'

export function readRememberedShopId(): string {
  try {
    return localStorage.getItem(KEY)?.trim() || ''
  } catch {
    return ''
  }
}

export function rememberShopId(slug: string): void {
  try {
    const cleaned = slug.trim().toLowerCase()
    if (cleaned) localStorage.setItem(KEY, cleaned)
  } catch {
    /* ignore private mode / blocked storage */
  }
}

export function forgetShopId(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* ignore */
  }
}
