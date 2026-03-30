/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { clearStoredTokens, getAuthSession, getStoredAccessToken, getStoredRefreshToken, refreshAuth, setStoredTokens, switchActiveSite, type FeatureKey, type PlanCode, type SiteOption } from '@/lib/api'

interface AuthCtx {
  token: string | null
  role: string | null
  tenantId: string | null
  /** Set after a successful `/auth/session` load; null when logged out or session not ready. */
  sessionUserId: string | null
  activeSiteTenantId: string | null
  availableSites: SiteOption[]
  planCode: PlanCode
  enabledFeatures: FeatureKey[]
  /** True when signup finished but Stripe subscription not confirmed yet (API returns subscription_required). */
  signupPaymentPending: boolean
  /** True after /auth/session succeeds for the current token (tenant, plan, features loaded). */
  sessionReady: boolean
  /** True while session is loading and the UI should block (not shown on / or /pricing while validating in background). */
  initializing: boolean
  login: (accessToken: string, refreshToken?: string | null, expiresInSeconds?: number) => void
  logout: () => void
  hasFeature: (feature: FeatureKey) => boolean
  refreshSession: () => Promise<void>
  switchSite: (tenantId: string) => Promise<void>
}

const AuthContext = createContext<AuthCtx | null>(null)
/** Must exceed `/auth/session` axios timeout so we do not clear the token while the request is still in flight. */
const SESSION_INIT_TIMEOUT_MS = 30_000

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

/** Marketing pages where we validate the JWT in the background without blocking the hero/pricing UI. */
function isSessionDeferPath(pathname: string) {
  return pathname === '/' || pathname === '/pricing'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
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
  const [sessionUserId, setSessionUserId] = useState<string | null>(null)
  const [activeSiteTenantId, setActiveSiteTenantId] = useState<string | null>(null)
  const [availableSites, setAvailableSites] = useState<SiteOption[]>([])
  const [planCode, setPlanCode] = useState<PlanCode>('pro')
  const [enabledFeatures, setEnabledFeatures] = useState<FeatureKey[]>(defaultFeatures)
  const [signupPaymentPending, setSignupPaymentPending] = useState(false)
  const [sessionReady, setSessionReady] = useState(() => !getStoredAccessToken())

  const initializing = useMemo(
    () => Boolean(token && !sessionReady && !isSessionDeferPath(location.pathname)),
    [token, sessionReady, location.pathname],
  )

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
      setSessionUserId(null)
      setActiveSiteTenantId(null)
      setAvailableSites([])
      setPlanCode('pro')
      setEnabledFeatures(defaultFeatures)
      setSignupPaymentPending(false)
      clearStoredTokens()
      return
    }
    const { data } = await getAuthSession()
    setRole(data.user.role)
    setTenantId(data.tenant_id)
    setSessionUserId(data.user.id)
    setActiveSiteTenantId(data.active_site_tenant_id)
    setAvailableSites(data.available_sites ?? [])
    setPlanCode(data.plan_code)
    setEnabledFeatures(data.enabled_features)
    setSignupPaymentPending(Boolean(data.signup_payment_pending))
  }

  useEffect(() => {
    function syncTokenFromStorage() {
      const nextToken = getStoredAccessToken()
      setToken(nextToken)
      setRole(parseRoleFromToken(nextToken))
      if (!nextToken) {
        setTenantId(null)
        setSessionUserId(null)
        setActiveSiteTenantId(null)
        setAvailableSites([])
        setPlanCode('pro')
        setEnabledFeatures(defaultFeatures)
        setSignupPaymentPending(false)
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

      setSessionReady(false)

      const timeoutId = setTimeout(() => {
        timedOut = true
        if (!canceled) {
          clearStoredTokens()
          setToken(null)
          setRole(null)
          setTenantId(null)
          setSessionUserId(null)
          setActiveSiteTenantId(null)
          setAvailableSites([])
          setPlanCode('pro')
          setEnabledFeatures(defaultFeatures)
          setSignupPaymentPending(false)
          setSessionReady(true)
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
            setSessionUserId(null)
            setActiveSiteTenantId(null)
            setAvailableSites([])
            setPlanCode('pro')
            setEnabledFeatures(defaultFeatures)
            setSignupPaymentPending(false)
          }
        } finally {
          clearTimeout(timeoutId)
          if (!canceled && !timedOut) setSessionReady(true)
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
      setSessionReady(true)
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
        setSessionUserId(null)
        setActiveSiteTenantId(null)
        setAvailableSites([])
        setPlanCode('pro')
        setEnabledFeatures(defaultFeatures)
        setSignupPaymentPending(false)
        setSessionReady(true)
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
          setSessionUserId(null)
          setActiveSiteTenantId(null)
          setAvailableSites([])
          setPlanCode('pro')
          setEnabledFeatures(defaultFeatures)
        }
      } finally {
        clearTimeout(timeoutId)
        // If dev login set a token, the [token] effect will load session; only unblock when still logged out.
        if (!canceled && !timedOut && !getStoredAccessToken()) setSessionReady(true)
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
    setSessionUserId(null)
    setActiveSiteTenantId(null)
    setAvailableSites([])
    setPlanCode('pro')
    setEnabledFeatures(defaultFeatures)
    setSignupPaymentPending(false)
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

  return (
    <AuthContext.Provider
      value={{
        token,
        role,
        tenantId,
        sessionUserId,
        activeSiteTenantId,
        availableSites,
        planCode,
        enabledFeatures,
        signupPaymentPending,
        sessionReady,
        initializing,
        login,
        logout,
        hasFeature,
        refreshSession,
        switchSite,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
