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
   * Keeps Stripe, Maps JS assets, and typical S3-style presigned hosts inside the WebView (Step 6).
   * Add your Stripe return / marketing hostname if it is not `mainspring.au`.
   */
  server: {
    allowNavigation: [
      '*.stripe.com',
      '*.*.stripe.com',
      'stripe.com',
      '*.googleapis.com',
      '*.gstatic.com',
      '*.google.com',
      '*.amazonaws.com',
      '*.*.amazonaws.com',
      '*.*.*.amazonaws.com',
      'mainspring.au',
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
