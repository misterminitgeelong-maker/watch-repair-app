import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { platformAdminEnterShop } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

/**
 * Platform-admin "enter shop" impersonation primitives.
 *
 * Extracted from PlatformAdminUsersPage so the always-rendered AppShell can
 * use AdminReturnBanner without statically importing the heavy admin page
 * (which defeated that page's lazy route split). The admin page imports
 * useAdminEnterShop from here.
 */

const ADMIN_PREV_TOKEN_KEY = 'admin_prev_token'
const ADMIN_PREV_REFRESH_KEY = 'admin_prev_refresh_token'
const ADMIN_IMPERSONATION_STARTED_KEY = 'admin_impersonation_started_at'
const ADMIN_IMPERSONATION_EXPIRES_KEY = 'admin_impersonation_expires_at'
const ADMIN_IMPERSONATION_DURATION_MS = 20 * 60 * 1000

function formatCountdown(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function useAdminEnterShop() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const [entering, setEntering] = useState('')
  const [error, setError] = useState('')

  async function enterShop(tenantId: string) {
    setEntering(tenantId)
    setError('')
    try {
      // Save current admin tokens so we can return
      const prevAccess = localStorage.getItem('token') ?? sessionStorage.getItem('token') ?? ''
      const prevRefresh = localStorage.getItem('refresh_token') ?? sessionStorage.getItem('refresh_token') ?? ''
      if (prevAccess) sessionStorage.setItem(ADMIN_PREV_TOKEN_KEY, prevAccess)
      if (prevRefresh) sessionStorage.setItem(ADMIN_PREV_REFRESH_KEY, prevRefresh)
      sessionStorage.setItem(ADMIN_IMPERSONATION_STARTED_KEY, String(Date.now()))
      sessionStorage.setItem(ADMIN_IMPERSONATION_EXPIRES_KEY, String(Date.now() + ADMIN_IMPERSONATION_DURATION_MS))

      const { data } = await platformAdminEnterShop(tenantId)

      // Use AuthContext login so tokens + role are set correctly
      authLogin(data.access_token, data.refresh_token, data.expires_in_seconds)
      await refreshSession()
      navigate('/dashboard')
    } catch {
      setError('Could not enter shop. Try again.')
    } finally {
      setEntering('')
    }
  }

  return { enterShop, entering, error }
}

export function AdminReturnBanner() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const prevToken = sessionStorage.getItem(ADMIN_PREV_TOKEN_KEY)
  const [nowMs, setNowMs] = useState(Date.now())
  const [returning, setReturning] = useState(false)

  const expiresAt = Number(sessionStorage.getItem(ADMIN_IMPERSONATION_EXPIRES_KEY) ?? '0')
  const remainingMs = expiresAt > 0 ? expiresAt - nowMs : 0

  useEffect(() => {
    if (!prevToken) return
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [prevToken])

  async function returnToAdmin() {
    if (returning) return
    setReturning(true)
    const prevAccess = sessionStorage.getItem(ADMIN_PREV_TOKEN_KEY) ?? ''
    const prevRefresh = sessionStorage.getItem(ADMIN_PREV_REFRESH_KEY) ?? ''
    sessionStorage.removeItem(ADMIN_PREV_TOKEN_KEY)
    sessionStorage.removeItem(ADMIN_PREV_REFRESH_KEY)
    sessionStorage.removeItem(ADMIN_IMPERSONATION_STARTED_KEY)
    sessionStorage.removeItem(ADMIN_IMPERSONATION_EXPIRES_KEY)
    if (prevAccess) {
      authLogin(prevAccess, prevRefresh || null)
      await refreshSession()
    }
    navigate('/platform-admin/users')
  }

  useEffect(() => {
    if (!prevToken) return
    if (remainingMs <= 0 && expiresAt > 0 && !returning) {
      void returnToAdmin()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prevToken, remainingMs, expiresAt, returning])

  if (!prevToken) return null

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between px-5 py-3 text-sm font-medium"
      style={{ backgroundColor: '#1F3A5F', color: '#E8F0FB' }}
    >
      <span>
        Viewing as Platform Admin. Session window {returning ? 'ending...' : formatCountdown(remainingMs)}.
      </span>
      <button
        className="ml-4 px-3 py-1.5 rounded-lg text-xs font-semibold"
        style={{ backgroundColor: '#4A7FC1', color: '#fff' }}
        onClick={() => void returnToAdmin()}
      >
        Return to Admin
      </button>
    </div>
  )
}
