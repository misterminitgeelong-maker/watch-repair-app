import { Capacitor } from '@capacitor/core'

/** Hostnames allowed for Universal Link → in-app navigation (comma-separated in VITE_UNIVERSAL_LINK_HOSTS). */
function allowedUniversalHosts(): Set<string> {
  const raw = (import.meta.env.VITE_UNIVERSAL_LINK_HOSTS as string | undefined)?.trim()
  const list = raw
    ? raw.split(',').map((h) => h.trim().toLowerCase()).filter(Boolean)
    : ['mainspring.au', 'www.mainspring.au']
  return new Set(list)
}

/**
 * If `url` is an https universal link to an allowed host, return the path + query + hash for React Router.
 * Otherwise return null (caller should ignore).
 */
export function inAppPathFromUniversalUrl(url: string): string | null {
  if (!Capacitor.isNativePlatform()) return null
  try {
    const u = new URL(url)
    if (u.protocol !== 'https:') return null
    const host = u.hostname.toLowerCase()
    if (!allowedUniversalHosts().has(host)) return null
    const path = `${u.pathname}${u.search}${u.hash}`
    return path || '/'
  } catch {
    return null
  }
}
