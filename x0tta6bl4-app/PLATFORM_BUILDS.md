# x0tta6bl4 Platform Builds

This app uses one React/Vite UI and native wrappers per platform:

- Android/iOS: Capacitor, app id `net.x0tta6bl4.mesh`
- Ubuntu/Windows desktop: Tauri v2, app id `net.x0tta6bl4.mesh`

## Backend Control Plane

The shared UI has two backend transports:

- Desktop Tauri: local commands read `/opt/x0tta6bl4-mesh`, Prometheus metrics, readiness gates, and can start/stop the local Core API on `127.0.0.1:8000`.
- Android/iOS/browser: HTTP fallback reads the same Core API through `VITE_CORE_API_BASE`.

Desktop start/stop currently uses `src.core.app_desktop:app` on `127.0.0.1:8000` by default. It gives the installed shell a fast local `/health` and `/status` surface plus read-only marketplace, billing, governance, agent-health, VPN, service-identity, mesh-status, and lightweight ledger-status endpoints. Override locally with `X0TTA6BL4_CORE_API_APP_MODULE=...` when testing another desktop-safe backend.

The Tauri launcher resolves the Python project root in this order:

1. `X0TTA6BL4_PROJECT_ROOT`, when set locally.
2. `/opt/x0tta6bl4`, the installed backend location used by the production installer.
3. `/mnt/projects`, the local development checkout fallback.

This keeps the `.deb` from being hard-wired to the development checkout while
still allowing local testing on this workstation.

If the full Python source tree is not installed, the Ubuntu `.deb` still ships
a standalone local API:

- `/usr/lib/x0tta6bl4/desktop_core_api.py`

The `START API` button prefers that packaged stdlib-only API when it exists.
It serves the read-only panel routes from local state so MESH, MARKET, BILLING,
WALLET, DAO, and OPS can render after installing the `.deb`. It does not execute
mutating production actions; those still require the full Core API and auth.

On Ubuntu, the MESH power button now attempts real local mesh service control
through systemd. The Tauri command is intentionally whitelisted to
`x0tta6bl4-node.service` and `x0t-agent.service`; it does not run arbitrary
shell commands. When those units are installed and the desktop user has
systemd/polkit permission, Start/Stop calls `systemctl start|stop` and then
refreshes runtime state from `/opt/x0tta6bl4-mesh/state/`. When the units are
missing or permission is denied, the app reports that exact blocker. Windows,
Android, and iOS keep using Core API/control-action routes instead of this
Linux-specific systemd path.

The Ubuntu `.deb` includes:

- `/usr/lib/systemd/system/x0tta6bl4-node.service`
- `/usr/lib/systemd/system/x0tta6bl4-core-api.service`
- `/usr/lib/systemd/system/x0tta6bl4-full-core-api.service`
- `/usr/lib/x0tta6bl4/desktop_core_api.py`
- `/usr/lib/x0tta6bl4/desktop_mesh_runtime.py`
- `/usr/lib/x0tta6bl4/start_full_core_api.sh`
- Debian maintainer scripts: `postinst`, `prerm`, and `postrm`

The package `postinst` script runs `systemctl daemon-reload`, enables, and
starts `x0tta6bl4-node.service` plus `x0tta6bl4-core-api.service`, so a normal
`.deb` install should leave both local backend services running. `prerm` stops
and disables those services on package removal, and `postrm` reloads systemd.

The node service is a local desktop node heartbeat. It writes
`runtime-state.json`, `client-profile-hint.json`, and
`listener-loss-signal.json` under `/opt/x0tta6bl4-mesh/state/` so the app has a
real local service to start, stop, and observe. Its claim boundary remains
local-only: it does not prove external dataplane delivery, customer traffic,
DPI bypass, settlement finality, or production readiness.

The desktop shell can now start the full Core API separately on `127.0.0.1:8001` with `src.core.app:app`. This keeps the UI responsive while exposing a clear attach point for the full platform router set. Override locally with `X0TTA6BL4_FULL_CORE_API_APP_MODULE=...`. Android/iOS/browser builds can point at that second backend with `VITE_FULL_CORE_API_BASE`.

The `.deb` also installs `x0tta6bl4-full-core-api.service` as an optional
systemd attach point for that backend. It is not enabled or started by
`postinst`; it has `ConditionPathExists=/opt/x0tta6bl4/src/core/app.py`, so it
stays inert until the full backend tree is installed. The desktop `START FULL`
button tries this unit before falling back to a development process.

Platform data panels use full-core-first reads. Marketplace, billing, wallet/ledger, governance, and agent-health data is requested from `VITE_FULL_CORE_API_BASE` / `127.0.0.1:8001` first, then from `VITE_CORE_API_BASE` / `127.0.0.1:8000` as a desktop-safe fallback. The UI labels the source for each panel so review can distinguish full-router data from fallback control-plane data.

The shared live status surface is:

```text
GET /api/v1/platform/live-snapshot
```

The desktop control-plane implements it by combining local runtime files, router
health, redacted EventBus summaries, and surface activity buckets for
marketplace, billing, wallet, DAO, OPS, mesh, and system events. The app
displays this as a shared live snapshot component in MESH, MARKET, WALLET, DAO,
OPS, and BILLING. The route is read-only and explicitly blocks
production-readiness, dataplane-delivery, customer-traffic, DPI-bypass, and
settlement-finality claims.

Platform action buttons also use full-core-first execution where the full backend already has safe read/prepare routes:

- Marketplace refresh: `GET /api/v1/maas/marketplace/status` and `GET /api/v1/maas/marketplace/search`.
- Billing prepare invoice: `GET /api/v1/maas/billing/billing/plans` and `GET /api/v1/maas/billing/billing/estimate`.
- Wallet open/search ledger: `GET /api/v1/ledger/status` and `GET /api/v1/ledger/search`.
- DAO prepare proposal/vote: `GET /api/v1/maas/governance/readiness` and `GET /api/v1/maas/governance/proposals`.
- MAPE-K health status: `GET /api/v1/maas/agents/health/status`.
- OPS identity: `GET /api/v1/service-identity/status`, `GET /api/v1/service-identity/event-trace-filter`, and `GET /api/v1/service-identity/event-traces`.
- OPS VPN/transport: `GET /api/v1/vpn/readiness`, `GET /api/v1/vpn/status`, and authenticated `GET /api/v1/vpn/users`.
- OPS provisioning/node diagnostics: `GET /api/v1/maas/provisioning/readiness`, `GET /api/v1/maas/nodes/{mesh_id}/nodes/pending`, `GET /api/v1/maas/nodes/{mesh_id}/nodes/all`, `GET /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/readiness`, and `GET /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/telemetry`.
- Readiness/VPN refresh: full-core readiness/status routes when available.

Payment, signing, proposal creation, voting, escrow release/refund, MAPE-K health execution, ledger indexing, and other mutating production operations are still not silently executed by the shell. They remain behind explicit full-core routes, auth/signing, and evidence gates.

The authenticated mutating full-core actions now wired:

- Create marketplace listing: `POST /api/v1/maas/marketplace/list`.
- Rent marketplace listing: `POST /api/v1/maas/marketplace/rent/{listing_id}`.
- Release/refund marketplace escrow: `POST /api/v1/maas/marketplace/escrow/{listing_id}/release` and `POST /api/v1/maas/marketplace/escrow/{listing_id}/refund`.
- Create billing payment intent: `POST /api/v1/maas/billing/billing/pay`.
- Index ledger, verification evidence, and EventBus traces: `POST /api/v1/ledger/index`, `POST /api/v1/ledger/evidence/index`, and `POST /api/v1/ledger/event-traces/index`.
- Run MAPE-K/MaaS health bot: `POST /api/v1/maas/agents/health/run`.
- Generate node setup package: `POST /api/v1/maas/provisioning/generate-setup`.
- Approve/revoke node: `POST /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/approve` and `POST /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/revoke`.
- Trigger node healing: `POST /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/heal`.
- Create DAO proposal: `POST /api/v1/maas/governance/proposals`.
- Cast DAO vote: `POST /api/v1/maas/governance/proposals/{proposal_id}/vote`.

The app sends `X-API-Key`, `Authorization: Bearer ...`, optional `Idempotency-Key`, and optional `X-Agent-Token` headers only from local UI/session state. `X-Agent-Token` is only needed for non-dry-run health-bot execution. The app does not store secret values in source files, docs, action result text, or logs. Operators must enter private credentials locally in the app/runtime.

Provisioning setup responses are a special local UI case. The app displays the
returned `install_command` and `config_json` after `generate-setup` succeeds so
the operator can copy them into the target node setup flow. These values contain
a one-time join token and must not be copied into chat, issue trackers,
documentation, or logs. The generic action summary only records response keys
and route metadata.

Marketplace rental responses are now carried forward as a local Rental Lifecycle
context. Full-core rent/release/refund responses return `listing_id`, `node_id`,
`mesh_id`, `escrow_id`, `escrow_status`, `listing_status`,
`node_assignment`, `heartbeat_snapshot`, `lifecycle_next_action`, and a claim
boundary for the native app. The app can refresh that same lifecycle state with
`GET /api/v1/maas/marketplace/rental/{listing_id}/lifecycle`. A successful rent
fills the escrow listing field plus the provisioning and node diagnostics
`mesh_id`/`node_id`, then shows the operator the next path: generate setup,
approve/observe the node, and release or refund escrow. This is not evidence of
dataplane delivery, external settlement finality, or production readiness.

The shared UI now auto-refreshes the active Rental Lifecycle after provisioning
setup, node pending/all reads, node readiness/telemetry reads, and node
approve/heal/revoke actions when an active marketplace `listing_id` is known.
The action result panel records the follow-up refresh status, so MARKET and OPS
do not silently drift after node operations.

With an active Rental Lifecycle and configured full-core auth, the shared UI
also polls `GET /api/v1/maas/marketplace/rental/{listing_id}/lifecycle` every
15 seconds. The lifecycle card exposes the poll status, timestamp, heartbeat
state, and next lifecycle action. If auth is missing, the poll is explicitly
marked `paused`.

After setup generation, the native UI auto-fills the returned `node_id` into
Node Diagnostics. Operators can then read pending/all node state, readiness, and
telemetry, or run authenticated approve/revoke/heal operations. Read results use
a redacted payload preview that strips tokens, runtime credentials, setup
commands, configs, and VPN links before display.

The shared app now uses the same control-action contract on every platform:

```text
GET  /api/v1/actions
POST /api/v1/actions/execute
```

Desktop Tauri calls these routes through the local `core_api_post` bridge. Android/iOS/browser builds call them through `VITE_CORE_API_BASE`. The current action set is intentionally local-safe: refresh mesh/VPN/marketplace snapshots, open ledger status, and prepare billing/DAO/readiness handoffs. The desktop action API never handles private keys, never writes payment state, and keeps production proof claims blocked unless the full Core API and required evidence are present.

Known backend blocker: the full `src.core.app:app` still has heavy startup cost. Its `/health/live` and `/status` responses are now fast after import, but importing the full router set can still exceed the desktop UX budget. The next backend step is lazy-loading or splitting the full router set so the default desktop app can graduate from `src.core.app_desktop:app` to the complete Core API.

Mobile builds must be built with a backend address the device can reach, for example:

```bash
VITE_CORE_API_BASE=http://192.0.2.10:8000 npm run android:build
```

For a separate full-core backend:

```bash
VITE_CORE_API_BASE=http://192.0.2.10:8000 \
VITE_FULL_CORE_API_BASE=http://192.0.2.10:8001 \
npm run android:build
```

If `VITE_CORE_API_BASE` is omitted, the app tries same-origin Core API endpoints. That is useful for web hosting behind one gateway, but not enough for a physical phone unless the gateway is reachable from the device.

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

To summarize the actual four-platform goal state from a downloaded audit report plus local iOS signing readiness:

```bash
python3 scripts/ops/check_native_release_goal_status.py \
  --audit-json .tmp/native-release-artifacts/x0tta6bl4-native-release-artifact-audit/native-release-artifact-audit.json \
  --check-github-secrets \
  --json
```

This command reports `goal_complete: true` only when Android, iOS, Ubuntu, and Windows are all complete in the release artifact audit. It also reports the missing local iOS signing inputs and missing iOS GitHub secret names without printing secret values.

After iOS signing secrets are configured, the final closeout command can trigger the hard release workflow, wait for it, download the release audit, and fail unless all four platforms are complete:

```bash
python3 scripts/ops/run_native_release_closeout.py \
  --trigger-workflow \
  --wait \
  --download-audit \
  --check-github-secrets \
  --require-complete \
  --json \
  --output .tmp/native-release-closeout/native-release-closeout.json
```

This is the final proof command for the native app goal. It does not create Apple certificates or provisioning profiles, and it does not print private signing values.

## Platform Notes

- Android builds locally after installing JDK 21 and Android SDK platform/build tools.
- Android release signing can be bootstrapped with `scripts/ops/prepare_android_signing_secrets.py`; this generates local signing material and can set the required GitHub secrets without printing private values.
- Ubuntu builds locally with Tauri v2 and WebKitGTK 4.1.
- iOS simulator and unsigned device builds prove the native wrapper compiles for Apple targets. A real installable device `.ipa` still requires macOS, Xcode, CocoaPods, and Apple signing secrets.
- Windows MSI requires a Windows build host. On Linux, Tauri exposes only Linux bundle targets such as `deb`, `rpm`, and `appimage`.
- Signing setup is documented in `SIGNING.md`.

## Next Control-Plane Work

The current shared app can display local mesh state, metrics, Core API status, endpoint probes, capability cards, local readiness snapshots, and real-response panels for marketplace, billing, wallet/ledger, governance, agent health, Service Identity/SPIFFE, VPN/transport, MaaS provisioning, and node diagnostics endpoints when those endpoints answer. It can also execute authenticated full-core actions for marketplace list/rent/escrow, billing payment intent, ledger indexing, event-trace indexing, MAPE-K health run, provisioning setup generation, node healing, DAO proposal creation, and DAO voting. The next implementation slices are:

1. Reduce full `src.core.app:app` import/startup time with lazy router loading or a split production router set.
2. Add signed wallet operations with no private key material in chat, docs, action result text, or UI logs.
3. Keep `src.core.app_desktop:app` as the native-app control-plane until full Core API startup is inside the desktop UX budget.
4. Replace lifecycle polling with a backend event stream when the full Core API exposes durable heartbeat/lifecycle events.
5. Expand Billing from payment intent into real subscription lifecycle actions behind explicit confirmation.
6. Add a Windows CI/build verification pass for the same shared UI and Tauri command surface.
7. Keep iOS last: sync is possible on Linux, but signed device `.ipa` remains blocked until macOS/Xcode/CocoaPods and Apple signing inputs are available.
