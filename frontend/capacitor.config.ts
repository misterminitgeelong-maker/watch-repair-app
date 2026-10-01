import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'au.mainspring.app',
  appName: 'Mainspring',
  webDir: 'dist',
  android: {
    // Production builds only talk to https://mainspring.au.
    allowMixedContent: false,
  },
  plugins: {
    // Route fetch/XHR through the native HTTP stack: the app's https://localhost origin
    // is not in the production CORS allow-list, and native requests need no CORS.
    CapacitorHttp: { enabled: true },
    SplashScreen: { launchShowDuration: 800, backgroundColor: '#1B2B3E' },
    PushNotifications: { presentationOptions: ['badge', 'sound', 'alert'] },
  },
}

export default config
