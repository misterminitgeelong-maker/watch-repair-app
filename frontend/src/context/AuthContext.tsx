import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { clearStoredTokens, getAuthSession, getStoredAccessToken, getStoredRefreshToken, refreshAuth, setStoredTokens, switchActiveSite, type FeatureKey, type PlanCode, type SiteOption } from '@/lib/api'

interface AuthCtx {
  token: string | null
  role: string | null
  tenantId: string | null
  activeSiteTenantId: string | null
  availableSites: SiteOption[]
  planCode: PlanCode
  enabledFeatures: FeatureKey[]
  initializing: boolean
  login: (accessToken: string, refreshToken?: string | null, expiresInSeconds?: number) => void
  logout: () => void
  hasFeature: (feature: FeatureKey) => boolean
  refreshSession: () => Promise<void>
  switchSite: (tenantId: string) => Promise<void>
}

const AuthContext = createContext<AuthCtx | null>(null)
const SESSION_INIT_TIMEOUT_MS = 5_000

/** Parses role from JWT for optional optimistic UI before /auth/session loads. Session data is the source of truth for role and permissions. */
function parseRoleFromToken(token: string | null): string | null {
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const payload = parts[1]
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4)
    const decoded = atob(padded)
    const parsed = JSON.parse(decoded) as { sub?: string }
    const subjectParts = (parsed.sub || '').split(':')
    return subjectParts.length >= 3 ? subjectParts[2] : null
  } catch {
    return null
  }
}

async function postJson<T>(url: string, payload: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    throw new Error(`${url} failed: ${res.status}`)
  }

  return res.json() as Promise<T>
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const defaultFeatures: FeatureKey[] = ['watch', 'shoe', 'auto_key', 'customer_accounts', 'multi_site', 'rego_lookup']
  const [token, setToken] = useState<string | null>(() => {
    try {
      return getStoredAccessToken()
    } catch {
      return null
    }
  })
  const [role, setRole] = useState<string | null>(() => parseRoleFromToken(getStoredAccessToken()))
  const proactiveRefreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [tenantId, setTenantId] = useState<string | null>(null)
  const [activeSiteTenantId, setActiveSiteTenantId] = useState<string | null>(null)
  const [availableSites, setAvailableSites] = useState<SiteOption[]>([])
  const [planCode, setPlanCode] = useState<PlanCode>('pro')
  const [enabledFeatures, setEnabledFeatures] = useState<FeatureKey[]>(defaultFeatures)
  const [initializing, setInitializing] = useState(true)

  function scheduleProactiveRefresh(expiresInSeconds: number) {
    if (proactiveRefreshTimer.current) clearTimeout(proactiveRefreshTimer.current)
    const ms = Math.max(60_000, Math.floor(expiresInSeconds * 0.9 * 1000))
    proactiveRefreshTimer.current = setTimeout(() => {
      proactiveRefreshTimer.current = null
      const rt = getStoredRefreshToken()
      if (!rt) return
      refreshAuth(rt)
        .then((res) => {
          setStoredTokens(res.data.access_token, res.data.refresh_token ?? null)
          setToken(res.data.access_token)
          setRole(parseRoleFromToken(res.data.access_token))
          const next = res.data.expires_in_seconds ?? 480 * 60
          scheduleProactiveRefresh(next)
        })
        .catch(() => {
          clearStoredTokens()
          window.dispatchEvent(new Event('auth:token-cleared'))
        })
    }, ms)
  }

  async function refreshSession() {
    const stored = getStoredAccessToken()
    if (!stored) {
      setRole(null)
      setTenantId(null)
      setActiveSiteTenantId(null)
      setAvailableSites([])
      setPlanCode('pro')
      setEnabledFeatures(defaultFeatures)
      clearStoredTokens()
      return
    }
    const { data } = await getAuthSession()
    setRole(data.user.role)
    setTenantId(data.tenant_id)
    setActiveSiteTenantId(data.active_site_tenant_id)
    setAvailableSites(data.available_sites ?? [])
    setPlanCode(data.plan_code)
    setEnabledFeatures(data.enabled_features)
  }

  useEffect(() => {
    function syncTokenFromStorage() {
      const nextToken = getStoredAccessToken()
      setToken(nextToken)
      setRole(parseRoleFromToken(nextToken))
      if (!nextToken) {
        setTenantId(null)
        setActiveSiteTenantId(null)
        setAvailableSites([])
        setPlanCode('pro')
        setEnabledFeatures(defaultFeatures)
      }
    }

    window.addEventListener('storage', syncTokenFromStorage)
    window.addEventListener('auth:token-cleared', syncTokenFromStorage)
    return () => {
      window.removeEventListener('storage', syncTokenFromStorage)
      window.removeEventListener('auth:token-cleared', syncTokenFromStorage)
    }
  }, [])

  useEffect(() => {
    if (token) {
      let canceled = false
      let timedOut = false

      const timeoutId = setTimeout(() => {
        timedOut = true
        if (!canceled) {
          clearStoredTokens()
          setToken(null)
          setRole(null)
          setTenantId(null)
          setActiveSiteTenantId(null)
          setAvailableSites([])
          setPlanCode('pro')
          setEnabledFeatures(defaultFeatures)
          setInitializing(false)
        }
      }, SESSION_INIT_TIMEOUT_MS)

      async function loadSession() {
        try {
          await refreshSession()
          if (canceled || timedOut) return
        } catch {
          if (!canceled && !timedOut) {
            clearStoredTokens()
            setToken(null)
            setRole(null)
            setTenantId(null)
            setActiveSiteTenantId(null)
            setAvailableSites([])
            setPlanCode('pro')
            setEnabledFeatures(defaultFeatures)
          }
        } finally {
          clearTimeout(timeoutId)
          if (!canceled && !timedOut) setInitializing(false)
        }
      }

      loadSession()
      return () => {
        canceled = true
        clearTimeout(timeoutId)
      }
    }

    const enableDevAutoLogin =
      import.meta.env.DEV && String(import.meta.env.VITE_ENABLE_DEV_AUTO_LOGIN ?? 'false') === 'true'

    if (!enableDevAutoLogin) {
      setInitializing(false)
      return
    }

    let canceled = false
    let timedOut = false

    const timeoutId = setTimeout(() => {
      timedOut = true
      if (!canceled) {
        clearStoredTokens()
        setToken(null)
        setRole(null)
        setTenantId(null)
        setActiveSiteTenantId(null)
        setAvailableSites([])
        setPlanCode('pro')
        setEnabledFeatures(defaultFeatures)
        setInitializing(false)
      }
    }, SESSION_INIT_TIMEOUT_MS)

    async function ensureTestSession() {
      try {
        // Optional dev helper for local demos and seeded datasets.
        const loginResp = await postJson<{ access_token: string; refresh_token?: string }>('/v1/auth/dev-auto-login', {})
        if (!canceled && !timedOut && loginResp.access_token) {
          setStoredTokens(loginResp.access_token, loginResp.refresh_token ?? null)
          setToken(loginResp.access_token)
          setRole(parseRoleFromToken(loginResp.access_token))
        }
      } catch {
        if (!canceled && !timedOut) {
          clearStoredTokens()
          setToken(null)
          setRole(null)
          setTenantId(null)
          setActiveSiteTenantId(null)
          setAvailableSites([])
          setPlanCode('pro')
          setEnabledFeatures(defaultFeatures)
        }
      } finally {
        clearTimeout(timeoutId)
        if (!canceled && !timedOut) setInitializing(false)
      }
    }

    ensureTestSession()
    return () => {
      canceled = true
      clearTimeout(timeoutId)
    }
  }, [token])

  function login(accessToken: string, refreshToken?: string | null, expiresInSeconds?: number) {
    setStoredTokens(accessToken, refreshToken ?? null)
    setToken(accessToken)
    setRole(parseRoleFromToken(accessToken))
    if (typeof expiresInSeconds === 'number' && expiresInSeconds > 0) scheduleProactiveRefresh(expiresInSeconds)
  }

  function logout() {
    if (proactiveRefreshTimer.current) clearTimeout(proactiveRefreshTimer.current)
    proactiveRefreshTimer.current = null
    clearStoredTokens()
    setToken(null)
    setRole(null)
    setTenantId(null)
    setActiveSiteTenantId(null)
    setAvailableSites([])
    setPlanCode('pro')
    setEnabledFeatures(defaultFeatures)
  }

  async function switchSite(nextTenantId: string) {
    const { data } = await switchActiveSite(nextTenantId)
    setStoredTokens(data.access_token, data.refresh_token ?? null)
    setToken(data.access_token)
    setRole(parseRoleFromToken(data.access_token))
    const exp = data.expires_in_seconds ?? 480 * 60
    if (exp > 0) scheduleProactiveRefresh(exp)
    await refreshSession()
  }

  function hasFeature(feature: FeatureKey) {
    if (role === 'platform_admin') return true
    return enabledFeatures.includes(feature)
  }

  return <AuthContext.Provider value={{ token, role, tenantId, activeSiteTenantId, availableSites, planCode, enabledFeatures, initializing, login, logout, hasFeature, refreshSession, switchSite }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
