import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Native shells for iOS / Android. Workflow:
 *   npm run build && npm run cap:sync
 *   npm run cap:open:android   # or cap:open:ios (macOS + Xcode)
 * Point the web build at your API with VITE_API_BASE_URL (see frontend/.env.example).
 */
const config: CapacitorConfig = {
  appId: 'au.mainspring.app',
  appName: 'Mainspring',
  webDir: 'dist',
  /**
   * Without allowNavigation, Capacitor sends many external navigations to the system browser.
   * Entries are hostname masks (`*` = one DNS label), same rules as Capacitor Android HostMask.
   * Every entry here can load JavaScript inside the WebView — keep the list
   * as small as possible and remove anything you are not actively using.
   *
   * Stripe:    Checkout, Connect onboarding return, js.stripe.com assets.
   * Google:    Maps JS + static tile/asset hosts used by MobileServicesMap.
   * mainspring.au: Public marketing / Stripe return URL.
   *
   * S3 (*.amazonaws.com) was previously allowlisted for "typical S3-style
   * presigned hosts" but the app does not fetch from S3 — attachments are
   * served from the backend same-origin. Remove to shrink attack surface
   * (F-H1). Re-add a *specific* bucket hostname if that changes.
   */
  server: {
    allowNavigation: [
      'stripe.com',
      '*.stripe.com',
      'js.stripe.com',
      'checkout.stripe.com',
      'connect.stripe.com',
      'maps.googleapis.com',
      'maps.gstatic.com',
      'fonts.googleapis.com',
      'fonts.gstatic.com',
      'mainspring.au',
      'www.mainspring.au',
    ],
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      launchShowDuration: 400,
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#2D231C',
    },
  },
}

export default config
