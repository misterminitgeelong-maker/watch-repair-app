/** Injected at build time (see vite.config.ts / Dockerfile). */
export const APP_BUILD_ID =
  (import.meta.env.VITE_APP_BUILD_ID as string | undefined)?.trim() || 'dev'

export function stampBuildMetaTag(): void {
  if (typeof document === 'undefined') return
  let el = document.querySelector('meta[name="app-build"]') as HTMLMetaElement | null
  if (!el) {
    el = document.createElement('meta')
    el.name = 'app-build'
    document.head.appendChild(el)
  }
  el.content = APP_BUILD_ID
}
