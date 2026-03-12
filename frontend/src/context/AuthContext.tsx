import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getAuthSession, switchActiveSite, type FeatureKey, type PlanCode, type SiteOption } from '@/lib/api'

interface AuthCtx {
  token: string | null
  role: string | null
  tenantId: string | null
  activeSiteTenantId: string | null
  availableSites: SiteOption[]
  planCode: PlanCode
  enabledFeatures: FeatureKey[]
  initializing: boolean
  login: (token: string) => void
  logout: () => void
  hasFeature: (feature: FeatureKey) => boolean
  refreshSession: () => Promise<void>
  switchSite: (tenantId: string) => Promise<void>
}

const AuthContext = createContext<AuthCtx | null>(null)

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
  const defaultFeatures: FeatureKey[] = ['watch', 'shoe', 'auto_key', 'customer_accounts', 'multi_site']
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [role, setRole] = useState<string | null>(() => parseRoleFromToken(localStorage.getItem('token')))
  const [tenantId, setTenantId] = useState<string | null>(null)
  const [activeSiteTenantId, setActiveSiteTenantId] = useState<string | null>(null)
  const [availableSites, setAvailableSites] = useState<SiteOption[]>([])
  const [planCode, setPlanCode] = useState<PlanCode>('enterprise')
  const [enabledFeatures, setEnabledFeatures] = useState<FeatureKey[]>(defaultFeatures)
  const [initializing, setInitializing] = useState(true)

  async function refreshSession() {
    if (!localStorage.getItem('token')) {
      setRole(null)
      setTenantId(null)
      setActiveSiteTenantId(null)
      setAvailableSites([])
      setPlanCode('enterprise')
      setEnabledFeatures(defaultFeatures)
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
      const nextToken = localStorage.getItem('token')
      setToken(nextToken)
      setRole(parseRoleFromToken(nextToken))
      if (!nextToken) {
        setTenantId(null)
        setActiveSiteTenantId(null)
        setAvailableSites([])
        setPlanCode('enterprise')
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

      async function loadSession() {
        try {
          await refreshSession()
          if (canceled) return
        } catch {
          localStorage.removeItem('token')
          if (!canceled) {
            setToken(null)
            setRole(null)
            setTenantId(null)
            setActiveSiteTenantId(null)
            setAvailableSites([])
            setPlanCode('enterprise')
            setEnabledFeatures(defaultFeatures)
          }
        } finally {
          if (!canceled) setInitializing(false)
        }
      }

      loadSession()
      return () => {
        canceled = true
      }
    }

    const enableDevAutoLogin =
      import.meta.env.DEV && String(import.meta.env.VITE_ENABLE_DEV_AUTO_LOGIN ?? 'false') === 'true'

    if (!enableDevAutoLogin) {
      setInitializing(false)
      return
    }

    let canceled = false

    async function ensureTestSession() {
      try {
        // Optional dev helper for local demos and seeded datasets.
        const loginResp = await postJson<{ access_token: string }>('/v1/auth/dev-auto-login', {})
        if (!canceled && loginResp.access_token) {
          localStorage.setItem('token', loginResp.access_token)
          setToken(loginResp.access_token)
          setRole(parseRoleFromToken(loginResp.access_token))
        }
      } catch {
        // Leave unauthenticated if setup fails.
        localStorage.removeItem('token')
        if (!canceled) {
          setToken(null)
          setRole(null)
          setTenantId(null)
          setActiveSiteTenantId(null)
          setAvailableSites([])
          setPlanCode('enterprise')
          setEnabledFeatures(defaultFeatures)
        }
      } finally {
        if (!canceled) setInitializing(false)
      }
    }

    ensureTestSession()
    return () => {
      canceled = true
    }
  }, [token])

  function login(t: string) {
    localStorage.setItem('token', t)
    setToken(t)
    setRole(parseRoleFromToken(t))
  }

  function logout() {
    localStorage.removeItem('token')
    setToken(null)
    setRole(null)
    setTenantId(null)
    setActiveSiteTenantId(null)
    setAvailableSites([])
    setPlanCode('enterprise')
    setEnabledFeatures(defaultFeatures)
  }

  async function switchSite(nextTenantId: string) {
    const { data } = await switchActiveSite(nextTenantId)
    localStorage.setItem('token', data.access_token)
    setToken(data.access_token)
    setRole(parseRoleFromToken(data.access_token))
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
