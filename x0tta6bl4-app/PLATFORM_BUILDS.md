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
- iOS simulator app and unsigned iOS device app on a macOS runner, plus signed device `.ipa` when Apple signing secrets are configured.
- One manifest artifact per platform: `SHA256SUMS` and `native-build-manifest.json`.
- One signing readiness artifact: `x0tta6bl4-native-signing-readiness/native-signing-readiness.json`.
- One release audit artifact: `x0tta6bl4-native-release-artifact-audit/native-release-artifact-audit.json`.

The manifest files make each CI run auditable:

- `SHA256SUMS` contains the SHA-256 checksum for every uploaded native binary or package file.
- `native-build-manifest.json` records the platform, app id, GitHub run id, commit SHA, signing status, file sizes, and checksums.
- Android and iOS manifests explicitly show whether production signing material was present. If signing secrets are absent, unsigned Android release APK plus iOS simulator/device app bundles are still built, but signed Android AAB/IPA are not claimed.
- `native-signing-readiness.json` records which required signing secret names are present or missing without printing secret values.
- `native-release-artifact-audit.json` verifies the downloaded platform artifacts against their manifests. It marks the release incomplete until Android APK/AAB, Windows MSI, Ubuntu deb/AppImage, and a signed iOS `.ipa` are all present.

To audit a downloaded native run locally:

```bash
gh run download <run-id> --repo x0tta6bl4-ai/x0tta6bl4 --dir .tmp/native-release-artifacts
python3 scripts/ops/verify_native_release_artifacts.py \
  --artifact-root .tmp/native-release-artifacts \
  --json \
  --output .tmp/native-release-audit/native-release-artifact-audit.json
```

For a hard release gate, add `--require-complete`. The command exits with code `2` when any required platform artifact is missing, including the signed iOS `.ipa`.

To prepare and trigger the missing signed iOS release path after receiving the Apple `.cer` and `.mobileprovision`, use:

```bash
python3 scripts/ops/run_ios_signed_release_setup.py \
  --prepare \
  --set-github-secrets \
  --trigger-workflow \
  --require-complete-release \
  --json
```

The default local input paths are under `~/.local/share/x0tta6bl4/ios-signing/`. The command redacts private values and does not claim platform completion until the native release artifact audit reports `complete: true`.

## Platform Notes

- Android builds locally after installing JDK 21 and Android SDK platform/build tools.
- Android release signing can be bootstrapped with `scripts/ops/prepare_android_signing_secrets.py`; this generates local signing material and can set the required GitHub secrets without printing private values.
- Ubuntu builds locally with Tauri v2 and WebKitGTK 4.1.
- iOS simulator and unsigned device builds prove the native wrapper compiles for Apple targets. A real installable device `.ipa` still requires macOS, Xcode, CocoaPods, and Apple signing secrets.
- Windows MSI requires a Windows build host. On Linux, Tauri exposes only Linux bundle targets such as `deb`, `rpm`, and `appimage`.
- Signing setup is documented in `SIGNING.md`.
