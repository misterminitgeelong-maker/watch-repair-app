# Mainspring phone app (Capacitor)

Wraps this React app for Android (`android/`) and iOS (`ios/`). The native shell calls https://mainspring.au directly.

- Build and sync: `npm run cap:sync`, then open `android/` in Android Studio (`npm run cap:android`) and run on an emulator.
- Android Studio needs `android/local.properties` with `sdk.dir=...` (git-ignored).
- Native differences live behind `src/lib/native.ts`: refresh tokens are stored on the device (the SameSite=Strict cookie cannot work from the app), the service worker is off, and `CapacitorHttp` sends requests natively because `https://localhost` is not in production CORS.
- Push notifications: built with `VITE_ENABLE_PUSH=true` the app registers with Firebase and posts its token to `POST /v1/me/devices`. The backend (`app/push.py`) sends a push for each new inbox alert once `FCM_SERVICE_ACCOUNT_JSON` (a Firebase service-account key, whole file as the value) is set; unset means no sending. Needs `android/app/google-services.json` from Firebase (git-ignored).
- iOS: project is generated; open on a Mac (`npx cap open ios`, needs CocoaPods). No signing set up.
- Store accounts and signing keys are not configured.
