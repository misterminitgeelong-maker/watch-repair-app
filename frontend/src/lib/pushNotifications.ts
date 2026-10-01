import { PushNotifications } from '@capacitor/push-notifications'
import { isNativeApp } from '@/lib/native'

/**
 * Ask for notification permission and register with the push service (native app only).
 * Android needs android/app/google-services.json from Firebase; without it registering
 * crashes the app, so this stays off until `VITE_ENABLE_PUSH=true` is set at build time.
 * `onToken` receives the device token to send to the backend once it can store it.
 */
export async function registerForPush(onToken: (token: string) => void): Promise<void> {
  if (!isNativeApp || String(import.meta.env.VITE_ENABLE_PUSH ?? 'false') !== 'true') return
  const perm = await PushNotifications.requestPermissions()
  if (perm.receive !== 'granted') return
  await PushNotifications.addListener('registration', (t) => onToken(t.value))
  await PushNotifications.addListener('registrationError', (e) => console.warn('Push registration failed', e))
  await PushNotifications.register()
}
