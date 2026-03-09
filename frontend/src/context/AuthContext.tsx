import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

interface AuthCtx {
  token: string | null
  initializing: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

const TEST_TENANT = 'myshop'
const TEST_EMAIL = 'admin@admin.com'
const TEST_PASSWORD = 'Admin'

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
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [initializing, setInitializing] = useState(true)

  useEffect(() => {
    let canceled = false

    async function ensureTestSession() {
      if (token) {
        if (!canceled) setInitializing(false)
        return
      }

      try {
        // Try login first in case tenant already exists.
        const loginResp = await postJson<{ access_token: string }>('/v1/auth/login', {
          tenant_slug: TEST_TENANT,
          email: TEST_EMAIL,
          password: TEST_PASSWORD,
        })
        if (!canceled && loginResp.access_token) {
          localStorage.setItem('token', loginResp.access_token)
          setToken(loginResp.access_token)
        }
      } catch {
        try {
          // If login fails, attempt bootstrap once then login.
          await postJson('/v1/auth/bootstrap', {
            tenant_name: 'My Shop',
            tenant_slug: TEST_TENANT,
            owner_email: TEST_EMAIL,
            owner_full_name: 'Admin',
            owner_password: TEST_PASSWORD,
          })
        } catch {
          // Ignore bootstrap conflicts/disabled state and try login regardless.
        }

        try {
          const loginResp = await postJson<{ access_token: string }>('/v1/auth/login', {
            tenant_slug: TEST_TENANT,
            email: TEST_EMAIL,
            password: TEST_PASSWORD,
          })
          if (!canceled && loginResp.access_token) {
            localStorage.setItem('token', loginResp.access_token)
            setToken(loginResp.access_token)
          }
        } catch {
          // Leave unauthenticated if setup fails.
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
  }

  function logout() {
    localStorage.removeItem('token')
    setToken(null)
  }

  return <AuthContext.Provider value={{ token, initializing, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
