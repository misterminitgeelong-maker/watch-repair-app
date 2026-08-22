const KEY = 'mainspring.justLoggedIn.v1'

/** Call right before navigating away from a successful login. Deliberately NOT carried via
 * react-router's navigate() `state` option — this app's post-login routing goes through one or
 * more client-side redirects before settling (LoginPage's own token-driven <Navigate>, FeatureGate
 * bouncing off /parent-account, MinitHqGate, etc.), any one of which can replace the history entry
 * and drop router state along the way. sessionStorage isn't tied to a specific history entry, so it
 * survives that redirect chain intact. */
export function markJustLoggedIn(): void {
  try {
    sessionStorage.setItem(KEY, '1')
  } catch {
    // Storage can throw in locked-down contexts (private browsing, etc.) — the gate just won't show.
  }
}

/** Non-destructive read — call from AppShell's lazy useState initializer. Deliberately does NOT
 * clear the flag: App.tsx's LocationBoundary keys its ErrorBoundary by location.pathname, so
 * AppShell itself unmounts/remounts on every pathname change, and the post-login redirect chain
 * above changes pathname 1-2 times before settling. Clearing on read would let the first,
 * short-lived AppShell instance consume the flag before the one that actually sticks around ever
 * saw it. Call clearJustLoggedIn() once the gate has genuinely finished instead. */
export function peekJustLoggedIn(): boolean {
  try {
    return sessionStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

/** Call once the loading gate has genuinely completed (not just because its AppShell instance is
 * about to unmount for another redirect) — so a later page refresh doesn't bring it back. */
export function clearJustLoggedIn(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Ignore — worst case the flag lingers for this tab's session and the gate shows once more.
  }
}
