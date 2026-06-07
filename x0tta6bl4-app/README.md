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

## Backend Connection

The app is now a shared control-plane UI:

- Tauri desktop builds call local backend commands through Tauri `invoke`.
- Android, iOS, and browser builds call the Core API over HTTP.

For mobile or browser builds, point the app at a reachable x0tta6bl4 Core API:

```bash
VITE_CORE_API_BASE=http://127.0.0.1:8000 npm run build
```

For a phone or emulator, replace `127.0.0.1` with the host or tunnel address that the device can reach. Do not put private tokens in this value.
If the full Core API is exposed separately, also set:

```bash
VITE_FULL_CORE_API_BASE=http://127.0.0.1:8001 npm run build
```

The Core API entrypoint is:

```bash
cd /opt/x0tta6bl4
PYTHONPATH=/opt/x0tta6bl4 MAAS_LIGHT_MODE=true \
python3 -m uvicorn src.core.app:app --host 127.0.0.1 --port 8000
```

For development checkouts, point the desktop launcher at the checkout root:

```bash
X0TTA6BL4_PROJECT_ROOT=/mnt/projects x0tta6bl4
```

Without an override, the Tauri launcher searches `/opt/x0tta6bl4` first and
falls back to `/mnt/projects` only on this local development machine.

For installed Ubuntu packages that do not yet include the full Python source
tree, the `.deb` also ships a standalone stdlib-only desktop Core API:

```text
/usr/lib/x0tta6bl4/desktop_core_api.py
```

The package installs and starts it through:

```text
x0tta6bl4-core-api.service
```

The Debian `postinst` script runs `systemctl daemon-reload`, enables the
desktop node service and Core API service, and starts them after installation.
The app's `START API` button still prefers that packaged API when it exists,
and falls back to an app-owned process only if systemd cannot start the unit.
It serves the local read-only panel routes (`/health`, `/status`,
`/mesh/status`, `/api/v1/platform/live-snapshot`, marketplace, billing,
wallet/ledger, DAO, VPN, service-identity, provisioning, and node diagnostics)
from local state. Mutating production work still requires the full Core API and
auth.

The installed Tauri desktop package starts a native-app control-plane by default:

```text
src.core.app_desktop:app
```

That keeps `/health` and `/status` responsive while exposing the real read-only marketplace, billing, governance, agent-health, VPN, service-identity, mesh-status, and lightweight ledger-status surfaces needed by the app. To force the full heavy Core API from the installed app during local testing, start the app with:

```bash
X0TTA6BL4_CORE_API_APP_MODULE=src.core.app:app x0tta6bl4
```

Known backend gap: the full `src.core.app:app` still has heavy startup cost. Its `/health/live` and `/status` responses were made fast after import, but importing the full router set can still exceed the desktop UX budget. Keep `src.core.app_desktop:app` as the default until the full app is lazy-loaded or split into smaller routers.

The MESH power button is wired to local Ubuntu systemd service control. It
checks only the known x0tta6bl4 units:

```text
x0tta6bl4-node.service
x0t-agent.service
```

The Ubuntu `.deb` now installs a local `x0tta6bl4-node.service` plus
`/usr/lib/x0tta6bl4/desktop_mesh_runtime.py`. The Debian `postinst` script
enables and starts both `x0tta6bl4-node.service` and
`x0tta6bl4-core-api.service`, so a normal install should leave the app with a
running local node heartbeat and Core API immediately. The node service writes
the local runtime files under `/opt/x0tta6bl4-mesh/state/`, so the installed app
can start, stop, and observe an actual local desktop node heartbeat. If a unit
is missing, systemd has not been reloaded, or the current desktop user has no
polkit/systemd permission, the app reports that directly instead of pretending
the mesh was started. This local heartbeat is intentionally not
production/dataplane proof.

The installed desktop app can also start the full Core API as a second local process:

```text
src.core.app:app on 127.0.0.1:8001
```

The `.deb` installs an optional unit for that attach point:

```text
x0tta6bl4-full-core-api.service
```

It is not enabled or started by `postinst`. It has
`ConditionPathExists=/opt/x0tta6bl4/src/core/app.py`, so it only starts when the
full backend tree is installed under `/opt/x0tta6bl4`. The UI `START FULL`
button tries that systemd unit first, then falls back to a local app-owned
process for development checkouts. This is intentionally separate from the fast
desktop control-plane on `127.0.0.1:8000`. The UI can show both states:
`Core API` for the responsive native shell backend and `Full Core API` for the
full platform router set. Override the full-core module during local testing
with `X0TTA6BL4_FULL_CORE_API_APP_MODULE`.

Marketplace, billing, wallet/ledger, governance, and agent-health panels now read with a full-core-first strategy:

1. Try `Full Core API` on `127.0.0.1:8001`.
2. Fall back to `Core API` on `127.0.0.1:8000` if the full route is unavailable.

Each data card shows its source, so the app does not hide whether it is showing full-router data or desktop control-plane fallback data.

Action buttons use the same rule. Snapshot/prepare/open actions first call real full-core routes such as marketplace status/search, billing estimate/plans, ledger status, governance readiness/proposals, readiness, and VPN readiness. If full-core is down, the app falls back to the desktop `/api/v1/actions/execute` handoff and labels the fallback reason in the action result.

The desktop control-plane also exposes a shared live state endpoint:

```text
GET /api/v1/platform/live-snapshot
```

The app reads it through the same full-core-first/fallback path and shows a
redacted EventBus feed, local runtime state, router health, surface activity
counts, and the claim boundary. MESH, MARKET, WALLET, DAO, OPS, and BILLING all
reuse the same live snapshot component with a surface filter, so each panel can
show relevant recent events without hiding the global platform state. This is an
operator visibility surface only: payload values are redacted and the endpoint
does not prove production readiness, dataplane delivery, customer traffic, DPI
bypass, or settlement finality.

For mutating full-core actions, enter credentials only inside the local app:

- `X-API-Key`
- or `Bearer token`
- optional `X-Agent-Token` for non-dry-run MAPE-K health-bot execution

The app keeps these values in the current browser/webview session storage and sends them as headers to full-core routes. It does not print token values in action results. Do not paste private tokens into chat or documentation.

Authenticated full-core actions currently wired in the app:

- `POST /api/v1/maas/marketplace/list`
- `POST /api/v1/maas/marketplace/rent/{listing_id}`
- `POST /api/v1/maas/marketplace/escrow/{listing_id}/release`
- `POST /api/v1/maas/marketplace/escrow/{listing_id}/refund`
- `POST /api/v1/maas/billing/billing/pay`
- `POST /api/v1/ledger/index`
- `POST /api/v1/ledger/evidence/index`
- `POST /api/v1/ledger/event-traces/index`
- `POST /api/v1/maas/agents/health/run`
- `POST /api/v1/maas/governance/proposals`
- `POST /api/v1/maas/governance/proposals/{proposal_id}/vote`

Marketplace rent/release/refund responses now return lifecycle fields for the
native app: `listing_id`, `node_id`, `mesh_id`, `escrow_id`, `escrow_status`,
`listing_status`, `node_assignment`, `heartbeat_snapshot`,
`lifecycle_next_action`, and a claim boundary. The app can also refresh the same
state through `GET /api/v1/maas/marketplace/rental/{listing_id}/lifecycle`.
After a rent succeeds, the MaaS tab keeps those backend-returned fields as
Rental Lifecycle context, opens OPS setup for the same mesh, checks pending
nodes, observes readiness and telemetry, then releases or refunds escrow. This
is still local API/DB lifecycle state only; it does not claim dataplane
delivery, external settlement finality, or production readiness.

The app auto-refreshes the active Rental Lifecycle after provisioning setup,
node pending/all reads, node readiness/telemetry reads, and node
approve/heal/revoke actions when an active `listing_id` is known. The action
result panel shows whether that follow-up refresh was `refreshed`, `skipped`,
or `failed`, so the operator can see whether MARKET and OPS are looking at the
same backend state.

When a Rental Lifecycle is active and full-core auth is configured, the app also
polls the lifecycle route every 15 seconds. The lifecycle card shows live poll
status, last poll time, heartbeat status, and the next lifecycle action. Without
full-core auth, live polling stays `paused` instead of pretending the backend is
attached.

Read-only full-core actions currently wired in the app:

- `GET /api/v1/maas/marketplace/status`
- `GET /api/v1/maas/marketplace/search`
- `GET /api/v1/maas/marketplace/rental/{listing_id}/lifecycle`
- `GET /api/v1/ledger/status`
- `GET /api/v1/ledger/search`
- `GET /api/v1/maas/agents/health/status`
- `GET /api/v1/service-identity/status`
- `GET /api/v1/service-identity/event-trace-filter`
- `GET /api/v1/service-identity/event-traces`
- `GET /api/v1/vpn/readiness`
- `GET /api/v1/vpn/status`
- `GET /api/v1/vpn/users`
- `GET /api/v1/maas/provisioning/readiness`
- `GET /api/v1/maas/nodes/{mesh_id}/nodes/pending`
- `GET /api/v1/maas/nodes/{mesh_id}/nodes/all`
- `GET /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/readiness`
- `GET /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/telemetry`
- `GET /api/v1/maas/governance/readiness`
- `GET /api/v1/maas/governance/proposals`

The `OPS` tab connects the app to platform operations surfaces:

- Service Identity / SPIFFE status and redacted event traces.
- VPN readiness, runtime status, and authenticated admin user listing.
- MaaS provisioning readiness and authenticated node setup generation.
- Node readiness, node telemetry, and authenticated node healing.

Authenticated OPS actions currently wired in the app:

- `POST /api/v1/maas/provisioning/generate-setup`
- `POST /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/approve`
- `POST /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/revoke`
- `POST /api/v1/maas/nodes/{mesh_id}/nodes/{node_id}/heal`

When `generate-setup` succeeds, the app shows the returned `install_command` and
`config_json` in a local-only Node Setup Package panel with copy buttons. Those
values contain a one-time join token. They are intentionally not written to
docs, logs, action summaries, or chat. Copy them only into the target node setup
flow.

After setup generation, the app auto-fills the generated `node_id` into the Node
Diagnostics form. Operators can then read pending/all nodes, readiness, and
telemetry, or run authenticated approve/revoke/heal actions. Read action results
show a redacted payload preview that removes tokens, credentials, install
commands, configs, and VPN links.

Desktop/mobile actions are exposed through:

```text
GET  /api/v1/actions
POST /api/v1/actions/execute
```

The action endpoint is deliberately safe by default. It can refresh local snapshots and prepare handoffs for marketplace, billing, wallet, DAO, readiness, and VPN surfaces, but it does not sign wallet operations, mutate chain state, submit payments, or claim production readiness. Mutating handoffs require the app to send `confirmation: "CONFIRM LOCAL ACTION"` locally; do not put private keys or tokens into action parameters.

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
