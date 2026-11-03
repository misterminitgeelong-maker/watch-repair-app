/**
 * Privacy-friendly visitor analytics (Cloudflare Web Analytics). Off unless configured.
 *
 * Set VITE_CF_ANALYTICS_TOKEN (the site token from Cloudflare) at build time to
 * turn it on. It is cookieless and does not fingerprint visitors. It follows
 * SPA route changes on its own. Skipped inside the native app, and when the
 * browser sends Do Not Track.
 */
export function initAnalytics(
  env: { token?: string } = { token: import.meta.env.VITE_CF_ANALYTICS_TOKEN },
  isNative = false,
): boolean {
  const token = env.token?.trim()
  if (!token || isNative || typeof document === 'undefined') return false
  if (navigator.doNotTrack === '1') return false
  if (document.querySelector('script[data-cf-beacon]')) return true

  const script = document.createElement('script')
  script.defer = true
  script.src = 'https://static.cloudflareinsights.com/beacon.min.js'
  script.setAttribute('data-cf-beacon', JSON.stringify({ token }))
  document.head.appendChild(script)
  return true
}
