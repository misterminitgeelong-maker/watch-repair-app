import axios from 'axios'

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
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
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

const api = axios.create({ baseURL: API_ORIGIN ? `${API_ORIGIN}/v1` : '/v1', timeout: 20000 })

// Attach JWT on every request
api.interceptors.request.use((config) => {
  const token = getStoredAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401: try refresh once, retry request; otherwise clear tokens
let refreshPromise: Promise<string | null> | null = null
function doRefresh(): Promise<string | null> {
  if (refreshPromise) return refreshPromise
  const rt = getStoredRefreshToken()
  if (!rt) {
    clearStoredTokens()
    window.dispatchEvent(new Event('auth:token-cleared'))
    return Promise.resolve(null)
  }
  refreshPromise = refreshAuth(rt)
    .then((res) => {
      const access = res.data.access_token
      const refresh = res.data.refresh_token ?? null
      setStoredTokens(access, refresh)
      emitAccessTokenUpdated(res.data.expires_in_seconds)
      return access
    })
    .catch(() => {
      clearStoredTokens()
      window.dispatchEvent(new Event('auth:token-cleared'))
      return null
    })
    .finally(() => {
      refreshPromise = null
    })
  return refreshPromise
}

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const status = err.response?.status
    const config = err.config
    if (status === 401 && config && !config._retried) {
      config._retried = true
      const newToken = await doRefresh()
      if (newToken) {
        config.headers.Authorization = `Bearer ${newToken}`
        return api.request(config)
      }
    } else if (status === 401) {
      clearStoredTokens()
      window.dispatchEvent(new Event('auth:token-cleared'))
    }
    if (!err.response && err.config && typeof navigator !== 'undefined' && !navigator.onLine) {
      const method = (err.config.method ?? 'get').toUpperCase()
      if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) {
        try {
          const { enqueueOffline } = await import('@/lib/offlineQueue')
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

export function setStoredTokens(accessToken: string, refreshToken: string | null) {
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
  localStorage.removeItem('token')
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  sessionStorage.removeItem('token')
  sessionStorage.removeItem(REFRESH_TOKEN_KEY)
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in_seconds?: number
  refresh_token?: string
  refresh_expires_in_seconds?: number
}
export const login = (tenant_slug: string, email: string, password: string) =>
  api.post<TokenResponse>('/auth/login', { tenant_slug, email, password })
export const refreshAuth = (refresh_token: string) =>
  api.post<TokenResponse>('/auth/refresh', { refresh_token })
