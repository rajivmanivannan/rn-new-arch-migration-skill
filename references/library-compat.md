# React Native New Architecture Library Compatibility Reference

This file contains known library compatibility status for New Architecture (TurboModules + Fabric).
Use during Step 1 of the audit. For libraries not listed here, mark as ❓ Unknown.

Sources: reactnative.directory, library changelogs, GitHub issues (as of early 2025).

---

## ✅ Compatible (confirmed New Arch support)

| Package | Notes |
|---------|-------|
| `react-native-reanimated` | >= 3.0. Full Fabric + TurboModule support |
| `react-native-gesture-handler` | >= 2.14. Fabric-compatible |
| `react-native-screens` | >= 3.29. Full New Arch support |
| `react-native-safe-area-context` | >= 4.8. New Arch ready |
| `@react-navigation/*` | >= 6.x (with compatible dependencies above) |
| `react-native-mmkv` | >= 2.11. JSI-based, New Arch native |
| `react-native-vision-camera` | >= 3.0. Full New Arch |
| `react-native-svg` | >= 14.0. Fabric support |
| `@shopify/flash-list` | Full Fabric support |
| `react-native-fast-image` | >= 8.6 with New Arch patch. Maintained fork: `@d11/react-native-fast-image` |
| `@d11/react-native-fast-image` | Community fork of react-native-fast-image. >= 8.13 targets New Arch via interop; full Fabric support in progress — check GitHub for latest |
| `react-native-permissions` | >= 3.10. TurboModule-based |
| `react-native-device-info` | >= 10.13. New Arch support |
| `react-native-share` | >= 10.0. New Arch ready |
| `react-native-image-picker` | >= 7.0. TurboModule-based |
| `react-native-camera-roll` | >= 7.5. New Arch ready |
| `react-native-haptic-feedback` | >= 2.2. New Arch ready |
| `react-native-localize` | >= 3.0. New Arch ready |
| `react-native-blob-util` | >= 0.19. New Arch support |
| `@notifee/react-native` | >= 7.8. New Arch support |
| `react-native-push-notification` | Deprecated — use @notifee instead |
| `lottie-react-native` | >= 6.0. Fabric support |
| `react-native-webview` | >= 13.6. New Arch support |
| `react-native-maps` | >= 1.10. Fabric support |
| `react-native-video` | >= 6.0. New Arch ready |
| `@react-native-community/netinfo` | >= 11.0. TurboModule-based |
| `@react-native-community/clipboard` | >= 1.5.1. New Arch ready |
| `@react-native-async-storage/async-storage` | >= 1.21. New Arch support |
| `react-native-keychain` | >= 8.2. TurboModule-based |
| `react-native-fs` | >= 2.20. New Arch support |
| `react-native-sqlite-storage` | Use `op-sqlite` or `expo-sqlite` instead for New Arch |
| `react-native-track-player` | >= 4.0. Fabric + TurboModule |
| `react-native-audio` | ⚠️ Partially — see notes below |

---

## ⚠️ Interop OK (works via interop layer, not natively upgraded)

These work when New Arch is enabled BUT rely on the interop compatibility layer. They should be migrated eventually.

| Package | Notes |
|---------|-------|
| `react-native-camera` | Interop only; migrate to `react-native-vision-camera` v3 |
| `react-native-linear-gradient` | Interop via compatibility shim; Fabric version in progress |
| `react-native-splash-screen` | Interop only; use `react-native-bootsplash` for full support |
| `react-native-snackbar` | Interop only |
| `react-native-modal` | Interop only for custom modal implementations |
| `react-native-ui-lib` | Interop OK, partial Fabric components |
| `react-native-paper` | Interop OK; full Fabric planned |
| `react-native-elements` | Interop OK |
| `react-native-rating` | Interop only |
| `react-native-star-rating-widget` | Interop only |
| `react-native-tooltip-menu` | Interop only |

---

## ❌ Blocking (no New Arch support — must replace or remove)

These will NOT work even with the interop layer. They block enabling New Arch.

| Package | Replacement |
|---------|-------------|
| `react-native-firebase` (v14 and below) | Upgrade to >= v18 which has New Arch support |
| `@react-native-firebase/app` (< 18) | Upgrade to >= 18 |
| `react-native-iap` (< 12) | Upgrade to >= 12.x |
| `react-native-blur` | Use `@react-native-community/blur` >= 4.4 |
| `react-native-swipeout` | Unmaintained; use `react-native-gesture-handler` swipeable |
| `react-native-tableview` | No New Arch support; use FlatList-based alternatives |
| `react-native-navigation` (Wix, < 7.37) | Upgrade to >= 7.37 or migrate to `react-native-screens` |
| `react-native-extended-stylesheet` | No New Arch support; use StyleSheet or styled-components |
| `react-native-picker` (deprecated) | Use `@react-native-picker/picker` >= 2.7 |
| `react-native-datepicker` | Unmaintained; use `@react-native-community/datetimepicker` |
| `react-native-progress` | No active New Arch support; use reanimated-based alternatives |
| `react-native-interactable` | Unmaintained; use Reanimated + Gesture Handler |
| `react-native-snap-carousel` (< 4) | Use `react-native-reanimated-carousel` |
| `react-native-animatable` | No New Arch support; migrate to Reanimated |
| `react-native-vector-icons` (< 10) | Upgrade to >= 10.0 for New Arch |

---

## Notes on major packages

### `react-native-firebase`
The `@react-native-firebase/*` family gained New Arch support in **v18**. If the project is on v14–v17, this is a **major upgrade** — check their v18 migration guide as there are breaking API changes.

### `react-native-navigation` (Wix)
Wix Navigation added New Arch support in 7.37.0 but it is experimental. The recommended path is to migrate to `react-navigation` + `react-native-screens` for full stability.

### `react-native-vector-icons`
v10+ added New Arch support but changed the import path. A find-replace across the codebase is required after upgrade.

### `react-native-sqlite-storage`
Effectively unmaintained for New Arch. Recommended replacements:
- `op-sqlite` — fastest, JSI-based
- `expo-sqlite` — if moving toward Expo modules
- `react-native-quick-sqlite` — good middle ground

### `react-native-audio`
Only partially compatible. Recording APIs work via interop; some playback APIs may be unstable. Evaluate `react-native-track-player` or `expo-av` as replacements.

---

## Packages that need no classification (pure JS, no native modules)

These have no native bridge usage and are unaffected by New Arch:

`lodash`, `axios`, `date-fns`, `moment`, `immer`, `zustand`, `jotai`, `recoil`, `redux`, `@reduxjs/toolkit`, `react-query`, `swr`, `formik`, `react-hook-form`, `yup`, `zod`, `i18next`, `react-i18next`, `@tanstack/*`, `clsx`, `classnames`, `uuid`, `nanoid`, `ramda`

Do not include these in the dependency audit table.
