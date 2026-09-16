import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { minitHqEnterShop, platformAdminEnterShop } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

/**
 * "Enter shop" impersonation primitives.
 *
 * Extracted from PlatformAdminUsersPage so the always-rendered AppShell can
 * use AdminReturnBanner without statically importing the heavy admin page
 * (which defeated that page's lazy route split). The admin page imports
 * useAdminEnterShop from here.
 *
 * There are two ways in, sharing one mechanism:
 *
 * - **Platform admin** — a support role over every tenant on the platform.
 * - **Minit HQ** — a Minit administrator supporting a shop in their own
 *   network. Authorisation comes from parent-account membership rather than a
 *   platform role, and the backend refuses anything that is not a Minit shop.
 *
 * Only one session can be borrowed at a time, so both use the same storage
 * keys; the label and return path are stored alongside so the banner can say
 * which hat the user is wearing and send them back where they came from.
 */

const PREV_TOKEN_KEY = 'admin_prev_token'
const PREV_REFRESH_KEY = 'admin_prev_refresh_token'
const STARTED_KEY = 'admin_impersonation_started_at'
const EXPIRES_KEY = 'admin_impersonation_expires_at'
const LABEL_KEY = 'admin_impersonation_label'
const RETURN_PATH_KEY = 'admin_impersonation_return_path'

const DEFAULT_LABEL = 'Platform Admin'
const DEFAULT_RETURN_PATH = '/platform-admin/users'

function formatCountdown(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

interface EnterShopResult {
  access_token: string
  refresh_token: string
  expires_in_seconds: number
}

/** Shared enter/return plumbing; the caller supplies the call and the framing. */
function useEnterShop(opts: {
  enter: (tenantId: string) => Promise<{ data: EnterShopResult }>
  label: string
  returnPath: string
  destination: string
  errorMessage: string
}) {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const [entering, setEntering] = useState('')
  const [error, setError] = useState('')

  async function enterShop(tenantId: string) {
    setEntering(tenantId)
    setError('')
    try {
      // Save current tokens so we can return.
      const prevAccess = localStorage.getItem('token') ?? sessionStorage.getItem('token') ?? ''
      const prevRefresh =
        localStorage.getItem('refresh_token') ?? sessionStorage.getItem('refresh_token') ?? ''
      if (prevAccess) sessionStorage.setItem(PREV_TOKEN_KEY, prevAccess)
      if (prevRefresh) sessionStorage.setItem(PREV_REFRESH_KEY, prevRefresh)

      const { data } = await opts.enter(tenantId)
      const windowMs = Math.max(1, data.expires_in_seconds) * 1000
      sessionStorage.setItem(STARTED_KEY, String(Date.now()))
      sessionStorage.setItem(EXPIRES_KEY, String(Date.now() + windowMs))
      sessionStorage.setItem(LABEL_KEY, opts.label)
      sessionStorage.setItem(RETURN_PATH_KEY, opts.returnPath)

      // Use AuthContext login so tokens + role are set correctly. An empty
      // refresh token must become null: stored as '', the refresh path would
      // try to redeem it. The HQ endpoint issues no refresh token by design.
      authLogin(data.access_token, data.refresh_token || null, data.expires_in_seconds)
      await refreshSession()
      navigate(opts.destination)
    } catch {
      setError(opts.errorMessage)
      // Do not leave a half-set impersonation behind.
      sessionStorage.removeItem(PREV_TOKEN_KEY)
      sessionStorage.removeItem(PREV_REFRESH_KEY)
    } finally {
      setEntering('')
    }
  }

  return { enterShop, entering, error }
}

export function useAdminEnterShop() {
  return useEnterShop({
    enter: platformAdminEnterShop,
    label: DEFAULT_LABEL,
    returnPath: DEFAULT_RETURN_PATH,
    destination: '/dashboard',
    errorMessage: 'Could not enter shop. Try again.',
  })
}

/** A Minit administrator opening one of their own network's shops. */
export function useMinitHqEnterShop() {
  return useEnterShop({
    enter: minitHqEnterShop,
    label: 'Minit Administrator',
    returnPath: '/minit/shops',
    destination: '/dashboard',
    errorMessage: 'Could not open that shop. It may have been deactivated.',
  })
}

export function AdminReturnBanner() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const prevToken = sessionStorage.getItem(PREV_TOKEN_KEY)
  const [nowMs, setNowMs] = useState(Date.now())
  const [returning, setReturning] = useState(false)

  const label = sessionStorage.getItem(LABEL_KEY) || DEFAULT_LABEL
  const expiresAt = Number(sessionStorage.getItem(EXPIRES_KEY) ?? '0')
  const remainingMs = expiresAt > 0 ? expiresAt - nowMs : 0

  useEffect(() => {
    if (!prevToken) return
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [prevToken])

  async function returnToAdmin() {
    if (returning) return
    setReturning(true)
    const prevAccess = sessionStorage.getItem(PREV_TOKEN_KEY) ?? ''
    const prevRefresh = sessionStorage.getItem(PREV_REFRESH_KEY) ?? ''
    const returnPath = sessionStorage.getItem(RETURN_PATH_KEY) || DEFAULT_RETURN_PATH
    sessionStorage.removeItem(PREV_TOKEN_KEY)
    sessionStorage.removeItem(PREV_REFRESH_KEY)
    sessionStorage.removeItem(STARTED_KEY)
    sessionStorage.removeItem(EXPIRES_KEY)
    sessionStorage.removeItem(LABEL_KEY)
    sessionStorage.removeItem(RETURN_PATH_KEY)
    if (prevAccess) {
      authLogin(prevAccess, prevRefresh || null)
      await refreshSession()
    }
    navigate(returnPath)
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
      style={{ backgroundColor: '#1F3A5F', color: '#E8F0FB', paddingBottom: 'max(0.75rem, calc(env(safe-area-inset-bottom) + 0.25rem))' }}
    >
      <span>
        Viewing as {label}. Session window {returning ? 'ending...' : formatCountdown(remainingMs)}.
      </span>
      <button
        className="ml-4 px-3 py-1.5 rounded-lg text-xs font-semibold"
        style={{ backgroundColor: '#4A7FC1', color: '#fff' }}
        onClick={() => void returnToAdmin()}
      >
        Return
      </button>
    </div>
  )
}
