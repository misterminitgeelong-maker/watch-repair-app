import axios, { type AxiosResponse } from 'axios'
import { enqueueOffline } from '@/lib/offlineQueue'
import { isNativeApp, NATIVE_API_ORIGIN } from '@/lib/native'
import { clearHqSupportSession, readParkedHqSession } from '@/lib/hqSupportSession'

/**
 * Optional API origin when the UI is served from a different host than the API (scheme + host, no path).
 * Set `VITE_API_BASE_URL` at build time, e.g. `https://mainspring.au` or `https://mainspring.au/v1`.
 * Leave unset for same-origin web: `/v1` (Vite dev proxy or Docker static + API).
 */
function normalizeConfiguredApiOrigin(raw: string): string {
  let s = raw.trim().replace(/\/+$/, '')
  if (s.toLowerCase().endsWith('/v1')) {
    s = s.slice(0, -3)
    s = s.replace(/\/+$/, '')
  }
  return s
}

export const API_ORIGIN: string = (() => {
  const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined) || (isNativeApp ? NATIVE_API_ORIGIN : undefined)
  if (!raw?.trim()) return ''
  return normalizeConfiguredApiOrigin(raw)
})()

/** Prefix a path that starts with `/v1` for cross-origin API calls when `VITE_API_BASE_URL` is set. */
export function withApiOrigin(v1Path: string): string {
  if (!v1Path.startsWith('/v1')) return v1Path
  return API_ORIGIN ? `${API_ORIGIN}${v1Path}` : v1Path
}

/** Fired after access token changes (401 refresh, login). Detail may include `expiresInSeconds` for proactive refresh scheduling. */
export const AUTH_ACCESS_TOKEN_UPDATED = 'auth:access-token-updated'

function emitAccessTokenUpdated(expiresInSeconds?: number): void {
  window.dispatchEvent(
    new CustomEvent<{ expiresInSeconds?: number }>(AUTH_ACCESS_TOKEN_UPDATED, {
      detail: expiresInSeconds != null && expiresInSeconds > 0 ? { expiresInSeconds } : {},
    }),
  )
}

// withCredentials: the refresh token lives in an httpOnly cookie on /v1/auth,
// which a cross-origin API (VITE_API_BASE_URL) only receives with credentials.
const api = axios.create({ baseURL: API_ORIGIN ? `${API_ORIGIN}/v1` : '/v1', timeout: 20000, withCredentials: true })

/**
 * Stored in place of a refresh token when the real one is in the httpOnly
 * `ms_refresh` cookie, where page scripts can't read it. Code that stashes and
 * restores "the refresh token" (impersonation, HQ enter-shop) carries this
 * marker through unchanged; `refreshAuth` sees it and lets the cookie do the work.
 */
export const REFRESH_VIA_COOKIE = '__cookie__'

/** Headers asking the API to deliver refresh tokens as an httpOnly cookie. */
export function refreshCookieHeaders(): Record<string, string> {
  // The native shell runs on a different site than the API, so the SameSite=Strict
  // refresh cookie would never be sent back; use body tokens held in local storage.
  if (isNativeApp) return {}
  return {
    'X-Auth-Refresh-Mode': 'cookie',
    // "Remember me" off → the server sets a browser-session cookie.
    'X-Auth-Remember': getRememberMe() ? '1' : '0',
  }
}

// Attach JWT on every request
api.interceptors.request.use((config) => {
  Object.assign(config, { _authSessionEpoch: authSessionEpoch })
  const token = getStoredAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  for (const [k, v] of Object.entries(refreshCookieHeaders())) config.headers[k] = v
  return config
})

// A token response whose refresh token went into the cookie: record the marker
// so every caller that stores `data.refresh_token` keeps working.
api.interceptors.response.use((res) => {
  const data = res.data as { refresh_in_cookie?: boolean; refresh_token?: string | null } | undefined
  if (data && typeof data === 'object' && data.refresh_in_cookie === true && !data.refresh_token) {
    data.refresh_token = REFRESH_VIA_COOKIE
  }
  return res
})

/** Pages a customer reaches by link, with no login of their own.
 *
 * Demo mode lingers in localStorage on a shared machine, so bouncing any
 * refresh failure to the demo login would throw a customer off the quote they
 * were approving or the invoice they were paying — pages that never needed a
 * session in the first place. */
const PUBLIC_PATH_PREFIXES = [
  '/login',
  '/signup',
  '/pricing',
  '/approve',
  '/shoe-approve',
  '/status',
  '/shoe-status',
  '/customer-portal',
  '/portal',
  '/mobile-booking',
  '/mobile-invoice',
  '/mobile-quote',
  '/mobile-job-intake',
  '/shop-invite',
  '/hq-invite',
  '/intake',
]

function isPublicPath(pathname: string): boolean {
  if (pathname === '/') return true
  return PUBLIC_PATH_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

// Refresh uses plain axios: the refresh endpoint must never enter its own
// 401 interceptor. Proactive and reactive callers share this same operation.
let authRevision = 0
let authSessionEpoch = 0
let refreshing: { revision: number; promise: Promise<AxiosResponse<TokenResponse>> } | null = null

export function isInvalidSessionError(error: unknown): boolean {
  return axios.isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)
}

function expireSession(): void {
  clearStoredTokens()
  window.dispatchEvent(new Event('auth:token-cleared'))
  try {
    if (localStorage.getItem('mainspring_demo_mode_enabled') === '1' && !isPublicPath(window.location.pathname)) {
      window.location.assign('/login?demo=1')
    }
  } catch { /* ignore storage restrictions */ }
}

async function doRefresh(): Promise<string | null> {
  const rt = getStoredRefreshToken()
  if (!rt) {
    // An HQ support session in a shop has no refresh token by design. When its
    // window closes, go back to the parked HQ login rather than signing out.
    const parked = readParkedHqSession()
    if (parked) {
      clearHqSupportSession()
      setStoredTokens(parked.access, parked.refresh)
      window.location.assign(parked.returnPath)
      return null
    }
    expireSession()
    return null
  }
  // Let transient refresh errors reject with their actual status (503/network),
  // rather than converting them to the original 401 and logging the user out.
  return (await refreshAuth(rt)).data.access_token
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const status = err.response?.status
    const config = err.config
    const authenticatedRequest = Boolean(config?.headers?.Authorization)
    const credentialEndpoint = /\/auth\/(login|multi-site-login|refresh|logout)(?:[/?]|$)/.test(config?.url ?? '')
    if (status === 401 && authenticatedRequest && config?._authSessionEpoch !== authSessionEpoch) {
      return Promise.reject(new axios.CanceledError('Session changed while request was in flight'))
    }
    if (status === 401 && authenticatedRequest && !credentialEndpoint && config && !config._retried) {
      config._retried = true
      const current = getStoredAccessToken()
      // Another request may already have refreshed while this 401 was in flight.
      const newerToken = current && config.headers.Authorization !== `Bearer ${current}` ? current : null
      const newToken = newerToken ?? await doRefresh()
      if (newToken) {
        config.headers.Authorization = `Bearer ${newToken}`
        return api.request(config)
      }
    }
    // A retried endpoint's 401 is not proof the refresh session is invalid.
    // Only the dedicated refresh endpoint can make that decision.
    if (!err.response && err.config && typeof navigator !== 'undefined' && !navigator.onLine) {
      const method = (err.config.method ?? 'get').toUpperCase()
      if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) {
        try {
          const url = err.config.url ?? ''
          await enqueueOffline({
            method,
            url: url.startsWith('http') ? url : `${err.config.baseURL ?? '/v1'}${url}`.replace(/\/v1\/v1/, '/v1'),
            body: err.config.data != null ? JSON.stringify(err.config.data) : null,
          })
        } catch {
          /* ignore queue errors */
        }
      }
    }
    return Promise.reject(err)
  }
)

export default api

export function getApiErrorMessage(error: unknown, fallback = 'Request failed.'): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const first = detail[0]
      if (typeof first === 'string' && first.trim()) return first
      if (first && typeof first === 'object' && typeof first.msg === 'string' && first.msg.trim()) {
        return first.msg
      }
    }
    if (error.response?.status === 401) return 'Session expired. Please sign in again.'
    if (error.response?.status === 402) return typeof detail === 'string' && detail.trim() ? detail : 'Plan limit reached. Upgrade for more capacity.'
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

/** True if the error is a 402 plan limit (show upgrade CTA). */
export function isPlanLimitError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 402
}

// ── Auth ──────────────────────────────────────────────────────────────────────
const REFRESH_TOKEN_KEY = 'refresh_token'
const REMEMBER_ME_KEY = 'remember_me'

export function getRememberMe(): boolean {
  // A phone app keeps you signed in; there is no browser session to end.
  if (isNativeApp) return true
  try {
    return localStorage.getItem(REMEMBER_ME_KEY) === 'true'
  } catch {
    return true
  }
}

export function setRememberMe(value: boolean) {
  try {
    if (value) localStorage.setItem(REMEMBER_ME_KEY, 'true')
    else localStorage.removeItem(REMEMBER_ME_KEY)
  } catch {
    /* ignore */
  }
}

function getTokenStorage(): Storage {
  return getRememberMe() ? localStorage : sessionStorage
}

export function getStoredAccessToken(): string | null {
  return getTokenStorage().getItem('token') ?? localStorage.getItem('token') ?? sessionStorage.getItem('token')
}

export function getStoredRefreshToken(): string | null {
  return getTokenStorage().getItem(REFRESH_TOKEN_KEY) ?? localStorage.getItem(REFRESH_TOKEN_KEY) ?? sessionStorage.getItem(REFRESH_TOKEN_KEY)
}

/** Fired when a sign-in stores fresh tokens (unlike the event above, not on silent refreshes). */
export const AUTH_TOKENS_STORED = 'auth:tokens-stored'

export function setStoredTokens(accessToken: string, refreshToken: string | null) {
  authSessionEpoch += 1
  writeStoredTokens(accessToken, refreshToken)
  window.dispatchEvent(new Event(AUTH_TOKENS_STORED))
}

function writeStoredTokens(accessToken: string, refreshToken: string | null) {
  authRevision += 1
  const storage = getTokenStorage()
  storage.setItem('token', accessToken)
  if (refreshToken != null) storage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  else storage.removeItem(REFRESH_TOKEN_KEY)
  if (storage === localStorage) {
    sessionStorage.removeItem('token')
    sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  } else {
    localStorage.removeItem('token')
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  }
}

export function clearStoredTokens() {
  authSessionEpoch += 1
  authRevision += 1
  localStorage.removeItem('token')
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  sessionStorage.removeItem('token')
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
  // Signing out (or an expired login) ends any HQ support session too; left
  // behind, its banner would reappear on the next login.
  clearHqSupportSession()
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_seconds?: number
  refresh_token?: string
  refresh_expires_in_seconds?: number
  refresh_in_cookie?: boolean
}
export const login = (tenant_slug: string, email: string, password: string) =>
  api.post<TokenResponse>('/auth/login', { tenant_slug, email, password })
export function refreshAuth(refresh_token: string): Promise<AxiosResponse<TokenResponse>> {
  if (refreshing?.revision === authRevision) return refreshing.promise
  const revision = authRevision
  const expectedAccess = getStoredAccessToken()
  const expectedRefresh = getStoredRefreshToken()
  const sessionStillCurrent = () => revision === authRevision && expectedAccess === getStoredAccessToken() && expectedRefresh === getStoredRefreshToken()
  const promise = axios.post<TokenResponse>(
    `${api.defaults.baseURL}/auth/refresh`,
    refresh_token === REFRESH_VIA_COOKIE ? {} : { refresh_token },
    { timeout: 20000, withCredentials: true, headers: refreshCookieHeaders() },
  ).then((res) => {
    // Logout / login / site switching while a refresh was in flight must win.
    if (!sessionStillCurrent()) throw new axios.CanceledError('Session changed during refresh')
    if (res.data.refresh_in_cookie && !res.data.refresh_token) res.data.refresh_token = REFRESH_VIA_COOKIE
    writeStoredTokens(res.data.access_token, res.data.refresh_token ?? null)
    emitAccessTokenUpdated(res.data.expires_in_seconds)
    return res
  }).catch((error: unknown) => {
    if (sessionStillCurrent() && isInvalidSessionError(error)) expireSession()
    throw error
  }).finally(() => {
    if (refreshing?.promise === promise) refreshing = null
  })
  refreshing = { revision, promise }
  return promise
}
