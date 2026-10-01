import { Haptics, ImpactStyle } from '@capacitor/haptics'
import { StatusBar, Style } from '@capacitor/status-bar'
import { isNativeApp } from '@/lib/native'

const TAPPABLE = 'button, a[href], [role="button"], [role="tab"], summary'

/** Match the status bar icons to the active theme (dark icons on light screens, light icons on the dark theme). */
function syncStatusBar(): void {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark'
  StatusBar.setStyle({ style: dark ? Style.Dark : Style.Light }).catch(() => {})
}

/** Phone-only touches: a light buzz on taps and a status bar that follows the theme. */
export function installNativeUi(): void {
  if (!isNativeApp) return

  let last = 0
  document.addEventListener(
    'click',
    (event) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const el = target.closest(TAPPABLE)
      if (!el || el.closest('[disabled], [aria-disabled="true"]')) return
      const now = Date.now()
      if (now - last < 80) return
      last = now
      Haptics.impact({ style: ImpactStyle.Light }).catch(() => {})
    },
    true,
  )

  syncStatusBar()
  new MutationObserver(syncStatusBar).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
}
