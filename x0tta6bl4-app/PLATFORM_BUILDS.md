# x0tta6bl4 Platform Builds

This app uses one React/Vite UI and native wrappers per platform:

- Android/iOS: Capacitor, app id `net.x0tta6bl4.mesh`
- Ubuntu/Windows desktop: Tauri v2, app id `net.x0tta6bl4.mesh`

## Local Ubuntu Host Status

Verified on the local Linux host:

```bash
npm run build
JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 ANDROID_HOME=/usr/lib/android-sdk ANDROID_SDK_ROOT=/usr/lib/android-sdk npm run android:build
npm run ios:sync
npm run desktop:build:linux
npm run lint
```

Built artifacts:

- Android debug APK: `android/app/build/outputs/apk/debug/app-debug.apk`
- Android unsigned release APK: `android/app/build/outputs/apk/release/*.apk`
- Ubuntu deb: `../src-tauri/target/release/bundle/deb/x0tta6bl4_0.1.0_amd64.deb`
- Ubuntu AppImage: `../src-tauri/target/release/bundle/appimage/x0tta6bl4_0.1.0_amd64.AppImage`

## GitHub Actions Status

The `Native App Builds` workflow builds and uploads:

- Android debug/release APKs, plus signed release AAB when Android signing secrets are configured.
- Windows MSI on a Windows runner.
- Ubuntu deb/AppImage on an Ubuntu runner.
- iOS simulator app on a macOS runner, plus signed device `.ipa` when Apple signing secrets are configured.
- One manifest artifact per platform: `SHA256SUMS` and `native-build-manifest.json`.
- One signing readiness artifact: `x0tta6bl4-native-signing-readiness/native-signing-readiness.json`.

The manifest files make each CI run auditable:

- `SHA256SUMS` contains the SHA-256 checksum for every uploaded native binary or package file.
- `native-build-manifest.json` records the platform, app id, GitHub run id, commit SHA, signing status, file sizes, and checksums.
- Android and iOS manifests explicitly show whether production signing material was present. If signing secrets are absent, unsigned Android release APK and iOS simulator app are still built, but signed Android AAB/IPA are not claimed.
- `native-signing-readiness.json` records which required signing secret names are present or missing without printing secret values.

## Platform Notes

- Android builds locally after installing JDK 21 and Android SDK platform/build tools.
- Ubuntu builds locally with Tauri v2 and WebKitGTK 4.1.
- iOS sync works locally, but a real device `.ipa` requires macOS, Xcode, CocoaPods, and Apple signing secrets.
- Windows MSI requires a Windows build host. On Linux, Tauri exposes only Linux bundle targets such as `deb`, `rpm`, and `appimage`.
- Signing setup is documented in `SIGNING.md`.
