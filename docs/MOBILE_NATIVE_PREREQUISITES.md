# Native (Capacitor) prerequisites

Mainspring ships as a responsive web app and an installable PWA. No native
project exists in this repository, and none is added by the mobile web
workstream. This note records what a Capacitor wrapper would need, so the
decision can be made with the costs visible.

Nothing here is required for the PWA. It is the checklist for the day someone
decides an App Store / Play Store presence is worth the overhead.

## What the PWA already covers

- Install to home screen on Android (`beforeinstallprompt`) and iOS (Add to
  Home Screen guidance), standalone display, maskable and iOS icons.
- Offline app shell, cached read-only screens, and an offline page.
- Camera and gallery capture via `<input type="file" accept="image/*"
  capture="environment">`, which is what the three intake flows use.
- Draft preservation in `localStorage` and a mutation queue in IndexedDB.

## What a native wrapper would add

| Capability | PWA today | Needs native |
|---|---|---|
| Push notifications on iOS | Web Push works in iOS 16.4+ only for installed PWAs | Reliable push on all supported iOS versions |
| Background sync | Foreground only | True background upload/sync |
| Bluetooth label printing | Web Bluetooth (Chrome/Android only, no iOS Safari) | Niimbot printing from iPhones |
| Deep links from SMS | Normal https links | Custom scheme / app links |
| Store distribution | None | App Store and Play Store listings |

The Bluetooth gap is the one with real operational weight: `src/lib/niimbot.ts`
uses Web Bluetooth, so label printing already cannot work from an iPhone,
installed or not.

## Prerequisites before starting

1. **Accounts and signing**
   - Apple Developer Program membership, an App Store Connect app record,
     bundle identifier, distribution certificate and provisioning profiles.
   - Google Play Console account, an upload key and Play App Signing.
2. **Build pipeline**
   - macOS runner for iOS builds (Xcode); Linux runner is enough for Android.
   - Railway does not build native binaries — expect a separate CI (GitHub
     Actions with a macOS runner, Codemagic, or similar).
3. **Repository additions**
   - `@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`, `@capacitor/android`
     plus a `capacitor.config.ts`, and the generated `ios/` and `android/`
     projects (large, and they must be kept in sync with each web release).
   - The root ESLint config already ignores `android` and `ios`, which suggests
     an earlier attempt; those directories do not exist today.
4. **App behaviour to change**
   - The service worker is a no-op inside a Capacitor WebView; asset caching
     and the update strategy would move to the native bundle plus a live-update
     mechanism.
   - `API_BASE`/CORS must accept the `capacitor://localhost` origin.
   - Token storage should move from `localStorage` to a secure store
     (`@capacitor/preferences` at minimum, Keychain/Keystore preferably).
   - Safe-area handling stays, but status bar and splash screens need native
     assets generated from the existing brand files.
5. **Release process**
   - Store review adds days to every release; the web app currently deploys
     continuously. Plan a version-skew policy between the shipped native shell
     and the web bundle it loads.

## Recommendation

Stay on the PWA until one of these is true: iPhone label printing becomes a
requirement, push notifications become part of the operational workflow, or a
customer contractually requires a store listing. Each one is a concrete trigger;
"being in the App Store" on its own does not pay for the pipeline above.
