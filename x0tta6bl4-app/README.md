# x0tta6bl4 App

`x0tta6bl4-app` is the shared React/Vite interface for the native x0tta6bl4 mesh clients.

Native wrappers:

- Android and iOS: Capacitor, app id `net.x0tta6bl4.mesh`
- Windows and Ubuntu: Tauri v2, app id `net.x0tta6bl4.mesh`

## Common Checks

```bash
npm ci
npm run build
npm run lint
```

## Android

```bash
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
ANDROID_HOME=/usr/lib/android-sdk \
ANDROID_SDK_ROOT=/usr/lib/android-sdk \
npm run android:build
```

Unsigned release APK:

```bash
npm run android:release:unsigned
```

Signed release APK/AAB requires Android signing variables. See `SIGNING.md`.

## iOS

Linux can sync the native project:

```bash
npm run ios:sync
```

Real iOS builds require macOS/Xcode. The GitHub workflow builds an iOS simulator app and unsigned device app by default, then builds a signed device `.ipa` when Apple signing secrets are configured. See `SIGNING.md`.

## Desktop

Ubuntu:

```bash
npm run desktop:build:linux
```

Windows MSI:

```bash
npm run desktop:build:windows
```

The Windows command must run on a Windows host or CI runner.
