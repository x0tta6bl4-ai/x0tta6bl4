# x0tta6bl4 App Signing

The native build workflow always verifies installable development artifacts:

- Android debug APK and unsigned release APK
- Windows MSI
- Ubuntu deb and AppImage
- iOS simulator app

Production Android and iOS device artifacts require private signing material. Do not commit private keys, certificates, provisioning profiles, or passwords. Store them only as GitHub Actions secrets or local environment variables.

## Signing Readiness Preflight

Use the preflight command before expecting signed release artifacts. It reports only whether required values are present; it never prints secret values.

Check local Android/iOS environment variables:

```bash
python3 scripts/ops/check_native_signing_readiness.py --source env-local
```

Check GitHub repository secrets:

```bash
python3 scripts/ops/check_native_signing_readiness.py --source github --repo x0tta6bl4-ai/x0tta6bl4
```

Fail closed when a signed release is required:

```bash
python3 scripts/ops/check_native_signing_readiness.py --source github --repo x0tta6bl4-ai/x0tta6bl4 --require-ready
```

The `Native App Builds` workflow uploads `x0tta6bl4-native-signing-readiness/native-signing-readiness.json` on every run. If it says `ready: false`, Android/iOS signed release artifacts are intentionally skipped.

## Android Release Signing

Set these repository secrets to produce signed Android release APK/AAB artifacts:

- `X0T_ANDROID_KEYSTORE_BASE64`: base64-encoded Android keystore file
- `X0T_ANDROID_KEYSTORE_PASSWORD`: keystore password
- `X0T_ANDROID_KEY_ALIAS`: key alias inside the keystore
- `X0T_ANDROID_KEY_PASSWORD`: key password

If this is the first Android release key for the project, generate it locally and upload the required GitHub secrets without printing private values:

```bash
python3 scripts/ops/prepare_android_signing_secrets.py \
  --generate \
  --write-local-env \
  --set-github-secrets \
  --repo x0tta6bl4-ai/x0tta6bl4 \
  --json \
  --output .tmp/native-signing/android/android-signing-setup.json
```

The generated keystore and local env file are written under `.tmp/native-signing/android/` with owner-only permissions. Keep them backed up in a private password manager or secure vault. Losing the Android signing key can prevent users from upgrading already-installed release builds.

The helper intentionally uses the same password for the PKCS12 keystore and key entry. This matches Android Gradle signing behavior and avoids release packaging failures when Gradle opens the key.

Local signed build:

```bash
export ANDROID_KEYSTORE_PATH=/absolute/path/to/release.keystore
export ANDROID_KEYSTORE_PASSWORD='...'
export ANDROID_KEY_ALIAS='...'
export ANDROID_KEY_PASSWORD='...'
npm run android:release:signed
```

Local unsigned release check:

```bash
npm run android:release:unsigned
```

## iOS Device Signing

Set these repository secrets to produce a signed iOS `.ipa` artifact:

- `X0T_IOS_CERTIFICATE_P12_BASE64`: base64-encoded Apple signing certificate `.p12`
- `X0T_IOS_CERTIFICATE_PASSWORD`: certificate password
- `X0T_IOS_PROVISIONING_PROFILE_BASE64`: base64-encoded `.mobileprovision`
- `X0T_IOS_TEAM_ID`: Apple Developer Team ID
- `X0T_IOS_BUNDLE_ID`: optional, defaults to `net.x0tta6bl4.mesh`
- `X0T_IOS_EXPORT_METHOD`: optional, defaults to `ad-hoc`

Without those secrets, CI still builds and uploads the unsigned iOS simulator app. That proves the Xcode project and native wrapper compile, but it is not an installable iPhone `.ipa`.
