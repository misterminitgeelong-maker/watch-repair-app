/**
 * Privacy-friendly visitor analytics (Plausible). Off unless configured.
 *
 * Set VITE_PLAUSIBLE_DOMAIN (e.g. `mainspring.au`) at build time to turn it on.
 * Plausible is cookieless and stores no personal data. It follows SPA route
 * changes on its own, so no per-page calls are needed. Skipped inside the
 * native app, and when the browser sends Do Not Track.
 */
export function initAnalytics(
  env: { domain?: string; host?: string } = {
    domain: import.meta.env.VITE_PLAUSIBLE_DOMAIN,
    host: import.meta.env.VITE_PLAUSIBLE_HOST,
  },
  isNative = false,
): boolean {
  const domain = env.domain?.trim()
  if (!domain || isNative || typeof document === 'undefined') return false
  if (navigator.doNotTrack === '1') return false
  if (document.querySelector('script[data-plausible]')) return true

  // Self-hosted instances can set a custom origin; default is Plausible Cloud.
  const origin = (env.host?.trim() || 'https://plausible.io').replace(/\/+$/, '')
  const script = document.createElement('script')
  script.defer = true
  script.src = `${origin}/js/script.js`
  script.dataset.domain = domain
  script.setAttribute('data-plausible', '')
  document.head.appendChild(script)
  return true
}
