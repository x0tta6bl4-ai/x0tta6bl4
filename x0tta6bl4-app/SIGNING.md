# x0tta6bl4 App Signing

The native build workflow always verifies installable development artifacts:

- Android debug APK and unsigned release APK
- Windows MSI
- Ubuntu deb and AppImage
- iOS simulator app and unsigned iOS device app

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

If an Apple Distribution certificate does not exist yet, generate a CSR and private key locally first:

```bash
python3 scripts/ops/prepare_ios_distribution_certificate_request.py \
  --generate \
  --email-address "$APPLE_ID_EMAIL" \
  --json \
  --output .tmp/native-signing/ios/ios-distribution-csr.json
```

Upload the generated `.csr` file to Apple Developer Certificates, create an Apple Distribution certificate, then export a `.p12` that contains the downloaded certificate and the generated private key. Keep the private key under `~/.local/share/x0tta6bl4/ios-signing/` or another secure local vault; do not commit it.

If Apple Developer gives you a downloaded `.cer` certificate and you used the local CSR helper above, export the `.p12` locally without printing the certificate password:

```bash
python3 scripts/ops/prepare_ios_distribution_p12.py \
  --export \
  --certificate-cer /secure/path/apple-distribution.cer \
  --private-key ~/.local/share/x0tta6bl4/ios-signing/apple-distribution.key \
  --p12-output ~/.local/share/x0tta6bl4/ios-signing/apple-distribution.p12 \
  --p12-password "$X0T_IOS_CERTIFICATE_PASSWORD" \
  --json \
  --output .tmp/native-signing/ios/ios-distribution-p12.json
```

The helper accepts PEM or DER Apple certificate files, writes the `.p12` with owner-only permissions, and passes the `.p12` password to `openssl` through stdin so it is not exposed in process arguments.

Before uploading iOS signing secrets, verify that the `.p12`, provisioning profile, Apple Team ID, and bundle ID match each other:

```bash
python3 scripts/ops/verify_ios_signing_material.py \
  --verify \
  --certificate-p12 ~/.local/share/x0tta6bl4/ios-signing/apple-distribution.p12 \
  --certificate-password "$X0T_IOS_CERTIFICATE_PASSWORD" \
  --provisioning-profile /secure/path/x0tta6bl4.mobileprovision \
  --team-id "$X0T_IOS_TEAM_ID" \
  --bundle-id net.x0tta6bl4.mesh \
  --require-valid \
  --json \
  --output .tmp/native-signing/ios/ios-signing-material-verification.json
```

This preflight checks that the provisioning profile is not expired, has `get-task-allow` disabled for release/ad-hoc signing, contains the same certificate as the `.p12`, and matches the expected `net.x0tta6bl4.mesh` app identifier. It does not print the `.p12` password or export private keys.

CI runs the same verification before importing iOS signing material into the macOS keychain. When iOS signing secrets are present, the workflow uploads `x0tta6bl4-ios-signing-material-verification/ios-signing-material-verification.json`.

After Apple Developer gives you the `.cer` certificate and `.mobileprovision` profile, the full local-to-CI path can be run with one orchestrator. It exports the `.p12`, verifies the `.p12` and profile match, writes the required GitHub secrets through stdin, and can trigger the hard release workflow:

```bash
read -rsp 'iOS .p12 password: ' X0T_IOS_CERTIFICATE_PASSWORD; echo
export X0T_IOS_CERTIFICATE_PASSWORD
read -rp 'Apple Team ID: ' X0T_IOS_TEAM_ID
export X0T_IOS_TEAM_ID

python3 scripts/ops/run_ios_signed_release_setup.py \
  --prepare \
  --certificate-cer ~/.local/share/x0tta6bl4/ios-signing/apple-distribution.cer \
  --private-key ~/.local/share/x0tta6bl4/ios-signing/apple-distribution.key \
  --p12-output ~/.local/share/x0tta6bl4/ios-signing/apple-distribution.p12 \
  --provisioning-profile ~/.local/share/x0tta6bl4/ios-signing/x0tta6bl4.mobileprovision \
  --bundle-id net.x0tta6bl4.mesh \
  --export-method ad-hoc \
  --set-github-secrets \
  --trigger-workflow \
  --require-complete-release \
  --json
```

The orchestrator does not print the private key, `.p12` password, Team ID, or secret values. A triggered workflow is still only a release request: the release becomes complete only after `x0tta6bl4-native-release-artifact-audit/native-release-artifact-audit.json` reports `complete: true`.

If the Apple signing certificate and provisioning profile already exist locally, upload them without printing private values:

```bash
python3 scripts/ops/prepare_ios_signing_secrets.py \
  --prepare \
  --certificate-p12 /secure/path/ios-distribution.p12 \
  --certificate-password "$X0T_IOS_CERTIFICATE_PASSWORD" \
  --provisioning-profile /secure/path/x0tta6bl4.mobileprovision \
  --team-id "$X0T_IOS_TEAM_ID" \
  --bundle-id net.x0tta6bl4.mesh \
  --export-method ad-hoc \
  --set-github-secrets \
  --repo x0tta6bl4-ai/x0tta6bl4 \
  --json \
  --output .tmp/native-signing/ios/ios-signing-setup.json
```

The helper does not create Apple certificates and does not validate App Store trust or notarization. It only transfers existing local signing material into GitHub secrets through stdin and redacts secret values from reports.

Without those secrets, CI still builds and uploads the unsigned iOS simulator app and unsigned iOS device app. That proves the Xcode project and native wrapper compile for Apple simulator and device targets, but it is not an installable iPhone `.ipa`.
