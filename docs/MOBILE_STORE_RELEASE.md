# Mobile store release (steps 8–12)

End-to-end checklist for **CI/CD**, **QA**, **store listings**, **rollout**, and **post‑v1** options. The Capacitor app id is **`au.mainspring.app`**; production web host examples use **`mainspring.au`**.

---

## 8 — CI/CD (implemented in repo)

### Continuous integration (`.github/workflows/ci.yml`)

| Job | What it does |
|-----|----------------|
| `backend` | Python tests, Alembic, smoke scripts, seed checks. |
| `frontend` | `npm ci`, lint, tests, full `npm run build`, uploads **`frontend-dist`** artifact. |
| `capacitor_android` | Downloads `frontend-dist`, `npm ci`, `npx cap sync`, **`assembleDebug`**, uploads **`android-debug-apk`**. |

Android SDK is provisioned with **`android-actions/setup-android@v3`** (`platforms;android-35`, `build-tools;35.0.0`).

### Signed AAB for Play Console (`.github/workflows/android-release.yml`)

Manual workflow: **Actions → Android release bundle → Run workflow**.

Create these **repository secrets** (Settings → Secrets and variables → Actions):

| Secret | Purpose |
|--------|---------|
| `ANDROID_KEYSTORE_BASE64` | Base64 of your upload keystore `.jks` file. |
| `ANDROID_KEYSTORE_PASSWORD` | Keystore password. |
| `ANDROID_KEY_ALIAS` | Key alias (e.g. `upload`). |
| `ANDROID_KEY_PASSWORD` | Key password (often same as store password). |

Optional workflow input **`vite_api_base_url`**: set to your production API origin (e.g. `https://mainspring.au`) so the bundled WebView calls the live API.

Artifact: **`mainspring-android-release-aab`** → upload to **Play Console → Internal testing** first.

Local signing: copy `frontend/android/keystore.properties.example` to `keystore.properties`, place `upload.jks` beside it, then `./gradlew bundleRelease` from `frontend/android`.

### iOS (TestFlight / App Store)

There is **no** iOS build job in GitHub Actions yet (macOS runners, signing, and CocoaPods add maintenance cost). Recommended path:

1. **Mac with Xcode** — `cd frontend && npm ci && npm run build:vite && npx cap sync`.
2. **`cd frontend/ios/App && pod install`**.
3. Open **`frontend/ios/App/App.xcworkspace`**, select the **App** scheme, set **Signing & Capabilities** (team, automatic signing).
4. **Archive** → **Distribute App** → App Store Connect / TestFlight.

Optional later: add **`fastlane`** or **Xcode Cloud** in a separate change.

---

## 9 — QA matrix (devices & flows)

Run on **real hardware** before widening distribution.

### Devices (minimum)

| Tier | Examples |
|------|-----------|
| Android | One mid-range (e.g. Pixel / Samsung A-series), one older WebView (if you support minSdk 23, pick a representative device). |
| iOS | One current iPhone, one older supported OS if you extend deployment backward. |

### Flows (check each)

- [ ] Login, logout, **remember device** on/off, cold start still signed in.
- [ ] Watch job: list → detail → **photo** upload → status change → optional **print / PDF**.
- [ ] Shoe job: same pattern.
- [ ] Auto-key job: detail, photo, map if used.
- [ ] **Mobile Services** map (with valid Maps key + referrers).
- [ ] **Stripe**: plan upgrade (`window.open`), subscription checkout (`location.assign`), **return URL** lands in app (Universal Links / `allowNavigation`).
- [ ] **Universal Link**: tap `https://mainspring.au/...` from Mail/Notes → opens app on correct route.
- [ ] **Offline**: airplane mode → sensible errors, no white screen crash; back online → refresh works.
- [ ] **Upgrade**: install build N, then install N+1 over the top (Play internal / TestFlight).

---

## 10 — Store listings & compliance

### Screenshots (approximate requirements — confirm in each console)

| Store | Phone | Tablet / other |
|-------|--------|----------------|
| **Google Play** | At least **2** phone screenshots; max **8**. 16:9 or 9:16, min short edge **320 px**. | 7" / 10" tablet shots if you support tablets. |
| **Apple App Store** | **6.7"** and **6.5"** (and 5.5" if supporting older) — see **App Store Connect → Screenshots** for exact pixel sizes. | iPad if `TARGETED_DEVICE_FAMILY` includes tablet. |

Capture from **internal builds** on real devices (shows actual status bar / safe area).

### Copy templates (edit for your tone)

**Short description (Play, ~80 chars)**  
> Mainspring: watch, shoe, and mobile locksmith jobs for your shop—intake to invoice in one app.

**Full description (first paragraph)**  
> Mainspring is the workshop app for **watch repairs**, **shoe repairs**, and **mobile auto-key / locksmith** jobs. Manage customers, jobs, quotes, invoices, and mobile services from your phone with the same account as the web app.

**Keywords / promo text (Apple)**  
> repair shop, watch repair, shoe repair, locksmith, auto key, mobile services, quotes, invoices

### Privacy & data safety

- **Apple**: **App Privacy** nutrition labels in App Store Connect (data linked to user: account, diagnostics if you use Sentry, etc.).
- **Google**: **Data safety** form (similar categories; declare encryption in transit, account creation, optional Bluetooth for label printing).
- **Public URL**: privacy policy page (required); support email in listings.

### Well-known files

Replace placeholders in:

- `frontend/public/.well-known/apple-app-site-association` (**Team ID**).
- `frontend/public/.well-known/assetlinks.json` (**SHA-256** from Play App Signing).

---

## 11 — Rollout strategy

1. **Internal only** — Play *Internal testing* + TestFlight *Internal testers*; fix crashes for 1–2 weeks.
2. **Closed beta** — small trusted group; gather screenshots and wording feedback.
3. **Production** — staged rollout (Play %) or phased iOS release; **keep web deploys independent** unless you automate both.

Coordinate **versionCode** (Android) / **CFBundleShortVersionString** (iOS) bumps with store submission.

---

## 12 — Post‑v1 ideas (not committed)

| Idea | When |
|------|------|
| **Push notifications** (FCM + APNs + backend topics) | When shops need “job ready” pings in app. |
| **Stronger offline** (queued writes, read-through cache) | High complexity; measure demand first. |
| **Native BLE plugin** for Niimbot | If Web Bluetooth in WebView is insufficient on target devices. |
| **iOS CI** (Fastlane / Xcode Cloud) | When you want every `main` commit to produce an IPA automatically. |

---

## Quick links

- Capacitor workflow: `frontend/README.md` (Capacitor section + Steps 3–7).
- Deep links: same README **Step 7** + `frontend/public/.well-known/*`.
