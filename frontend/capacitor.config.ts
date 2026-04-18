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
}

export default config
