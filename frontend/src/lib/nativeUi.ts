import { App } from '@capacitor/app'
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

  // Android Back: close the open dialog first, then go back a page, and only
  // leave the app from the first screen. Without this, Back with a form open
  // navigates away and loses what was typed.
  App.addListener('backButton', ({ canGoBack }) => {
    if (document.querySelector('[role="dialog"][aria-modal="true"]')) {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
      return
    }
    if (canGoBack) window.history.back()
    else App.exitApp().catch(() => {})
  }).catch(() => {})

  syncStatusBar()
  new MutationObserver(syncStatusBar).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
}
