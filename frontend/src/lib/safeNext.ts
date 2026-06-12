/**
 * Validate a post-login `?next=` redirect target.
 *
 * Only same-origin absolute paths are allowed. Anything that could send the
 * user off-site after login — full URLs, protocol-relative `//host` paths,
 * or backslash tricks browsers normalise to `//` — is rejected and the caller
 * falls back to the default home path.
 */
export function safeNextPath(raw: string | null | undefined): string | null {
  if (!raw) return null
  // Must be an absolute in-app path…
  if (!raw.startsWith('/')) return null
  // …but not protocol-relative (`//evil.com`) or backslash-normalised (`/\evil`).
  if (raw.startsWith('//') || raw.startsWith('/\\')) return null
  return raw
}
