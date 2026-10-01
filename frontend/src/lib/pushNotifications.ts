import { PushNotifications } from '@capacitor/push-notifications'
import api, { AUTH_ACCESS_TOKEN_UPDATED, AUTH_TOKENS_STORED, getStoredAccessToken } from '@/lib/api/client'
import { isNativeApp } from '@/lib/native'

let deviceToken: string | null = null
let synced = false

/** Send the device token to the backend once per sign-in; the endpoint is idempotent. */
async function syncDeviceToken(): Promise<void> {
  if (!deviceToken) return
  if (!getStoredAccessToken()) {
    synced = false
    return
  }
  if (synced) return
  synced = true
  try {
    await api.post('/me/devices', { token: deviceToken, platform: 'android' })
  } catch {
    synced = false
  }
}

/**
 * Ask for notification permission, register with the push service and keep the backend
 * informed of this device's token (native app only).
 * Android needs android/app/google-services.json from Firebase; without it registering
 * crashes the app, so this stays off until `VITE_ENABLE_PUSH=true` is set at build time.
 */
export async function registerForPush(): Promise<void> {
  if (!isNativeApp || String(import.meta.env.VITE_ENABLE_PUSH ?? 'false') !== 'true') return
  const perm = await PushNotifications.requestPermissions()
  if (perm.receive !== 'granted') return
  await PushNotifications.addListener('registration', (t) => {
    deviceToken = t.value
    void syncDeviceToken()
  })
  await PushNotifications.addListener('registrationError', (e) => console.warn('Push registration failed', e))
  window.addEventListener(AUTH_ACCESS_TOKEN_UPDATED, () => void syncDeviceToken())
  window.addEventListener(AUTH_TOKENS_STORED, () => {
    synced = false // a fresh sign-in may be a different user on the same phone
    void syncDeviceToken()
  })
  await PushNotifications.register()
}
