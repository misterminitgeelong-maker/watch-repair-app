# Mainspring phone app (Capacitor)

Wraps this React app for Android (`android/`) and iOS (`ios/`). The native shell calls https://mainspring.au directly.

- Build and sync: `npm run cap:sync`, then open `android/` in Android Studio (`npm run cap:android`) and run on an emulator.
- Android Studio needs `android/local.properties` with `sdk.dir=...` (git-ignored).
- Native differences live behind `src/lib/native.ts`: refresh tokens are stored on the device (the SameSite=Strict cookie cannot work from the app), the service worker is off, and `CapacitorHttp` sends requests natively because `https://localhost` is not in production CORS.
- Push notifications: client code is in `src/lib/pushNotifications.ts` but is off until Firebase (`android/app/google-services.json`) and a backend device-token endpoint exist.
- iOS: project is generated; open on a Mac (`npx cap open ios`, needs CocoaPods). No signing set up.
- Store accounts and signing keys are not configured.
