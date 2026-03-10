import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

interface AuthCtx {
  token: string | null
  initializing: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

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
    if (token) {
      setInitializing(false)
      return
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
        }
      } catch {
        // Leave unauthenticated if setup fails.
        localStorage.removeItem('token')
        if (!canceled) setToken(null)
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
