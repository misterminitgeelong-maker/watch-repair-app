import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { enterLinkedShop } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

/**
 * HQ "open shop" support sessions.
 *
 * The parent-account equivalent of platform-admin impersonation: an HQ admin
 * opens a short session inside one of the network's own shops, works there as
 * that shop's owner, then returns to HQ. The HQ tokens are parked in
 * sessionStorage for the duration; the shop token has no refresh token, so the
 * window closes on its own after the server's expiry.
 *
 * Kept separate from adminImpersonation so the two banners never fight over
 * the same storage keys — a platform admin can enter HQ and then HQ can enter
 * a shop, and each "return" unwinds one level.
 */

const HQ_PREV_TOKEN_KEY = 'hq_prev_token'
const HQ_PREV_REFRESH_KEY = 'hq_prev_refresh_token'
const HQ_SESSION_EXPIRES_KEY = 'hq_enter_shop_expires_at'
const HQ_SESSION_SHOP_KEY = 'hq_enter_shop_name'
const HQ_RETURN_PATH_KEY = 'hq_enter_shop_return_path'

function formatCountdown(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000))
  const mins = Math.floor(total / 60)
  const secs = total % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

export function useHqEnterShop() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const [entering, setEntering] = useState('')
  const [error, setError] = useState('')

  async function enterShop(tenantId: string, returnPath = '/minit/accounts', reason?: string) {
    setEntering(tenantId)
    setError('')
    try {
      const prevAccess = localStorage.getItem('token') ?? sessionStorage.getItem('token') ?? ''
      const prevRefresh = localStorage.getItem('refresh_token') ?? sessionStorage.getItem('refresh_token') ?? ''
      if (prevAccess) sessionStorage.setItem(HQ_PREV_TOKEN_KEY, prevAccess)
      if (prevRefresh) sessionStorage.setItem(HQ_PREV_REFRESH_KEY, prevRefresh)
      sessionStorage.setItem(HQ_RETURN_PATH_KEY, returnPath)

      const { data } = await enterLinkedShop(tenantId, reason)
      const windowMs = Math.max(1, data.expires_in_seconds) * 1000
      sessionStorage.setItem(HQ_SESSION_EXPIRES_KEY, String(Date.now() + windowMs))
      sessionStorage.setItem(HQ_SESSION_SHOP_KEY, data.tenant_name)

      // No refresh token on purpose: the support window cannot be extended.
      authLogin(data.access_token, null, data.expires_in_seconds)
      await refreshSession()
      navigate('/dashboard')
    } catch {
      sessionStorage.removeItem(HQ_PREV_TOKEN_KEY)
      sessionStorage.removeItem(HQ_PREV_REFRESH_KEY)
      sessionStorage.removeItem(HQ_RETURN_PATH_KEY)
      setError('Could not open that shop. Try again.')
    } finally {
      setEntering('')
    }
  }

  return { enterShop, entering, error }
}

export function HqReturnBanner() {
  const navigate = useNavigate()
  const { login: authLogin, refreshSession } = useAuth()
  const prevToken = sessionStorage.getItem(HQ_PREV_TOKEN_KEY)
  const shopName = sessionStorage.getItem(HQ_SESSION_SHOP_KEY) ?? 'shop'
  const [nowMs, setNowMs] = useState(Date.now())
  const [returning, setReturning] = useState(false)

  const expiresAt = Number(sessionStorage.getItem(HQ_SESSION_EXPIRES_KEY) ?? '0')
  const remainingMs = expiresAt > 0 ? expiresAt - nowMs : 0

  useEffect(() => {
    if (!prevToken) return
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [prevToken])

  async function returnToHq() {
    if (returning) return
    setReturning(true)
    const prevAccess = sessionStorage.getItem(HQ_PREV_TOKEN_KEY) ?? ''
    const prevRefresh = sessionStorage.getItem(HQ_PREV_REFRESH_KEY) ?? ''
    const returnPath = sessionStorage.getItem(HQ_RETURN_PATH_KEY) || '/minit/accounts'
    sessionStorage.removeItem(HQ_PREV_TOKEN_KEY)
    sessionStorage.removeItem(HQ_PREV_REFRESH_KEY)
    sessionStorage.removeItem(HQ_SESSION_EXPIRES_KEY)
    sessionStorage.removeItem(HQ_SESSION_SHOP_KEY)
    sessionStorage.removeItem(HQ_RETURN_PATH_KEY)
    if (prevAccess) {
      authLogin(prevAccess, prevRefresh || null)
      await refreshSession()
    }
    navigate(returnPath)
  }

  useEffect(() => {
    if (!prevToken) return
    if (remainingMs <= 0 && expiresAt > 0 && !returning) {
      void returnToHq()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prevToken, remainingMs, expiresAt, returning])

  if (!prevToken) return null

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between px-5 py-3 text-sm font-medium"
      style={{
        backgroundColor: 'var(--ms-accent)',
        color: 'var(--ms-sidebar-act-text, #fff)',
        paddingBottom: 'max(0.75rem, calc(env(safe-area-inset-bottom) + 0.25rem))',
      }}
    >
      <span>
        HQ support session in {shopName}. Window {returning ? 'ending…' : formatCountdown(remainingMs)}.
      </span>
      <button
        className="ml-4 px-3 py-1.5 rounded-lg text-xs font-semibold"
        style={{ backgroundColor: 'rgba(255,255,255,0.18)', color: 'inherit' }}
        onClick={() => void returnToHq()}
      >
        Return to HQ
      </button>
    </div>
  )
}
