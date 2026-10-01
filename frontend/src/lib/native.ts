import { Capacitor } from '@capacitor/core'

/** True inside the Capacitor (Android/iOS) shell, false in a normal browser. */
export const isNativeApp: boolean = Capacitor.isNativePlatform()

/** API origin used by the native shell, which has no same-origin `/v1`. */
export const NATIVE_API_ORIGIN = 'https://mainspring.au'
