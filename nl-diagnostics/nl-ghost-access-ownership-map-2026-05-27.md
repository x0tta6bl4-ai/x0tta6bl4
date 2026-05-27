# NL Ghost Access Ownership Map, 2026-05-27

## Status

This map was built from redacted local review copies only.

```text
NL writes: 0
raw source saved locally: false
deployable: false
inputs:
  services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
  services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
```

The goal is to understand ownership boundaries before reconstructing clean
deployable source.

## File Roles

### issue_offline_subscription.py

Role:

```text
offline/admin provisioning helper
```

Observed structure:

```text
functions: 11
classes: 0
imports: argparse, json, os, secrets, sqlite3, subprocess, uuid
```

Key areas:

```text
claim code generation
subscription token generation
sqlite table setup
xray/profile command execution
VLESS/XHTTP link building
base URL assembly
CLI argument parsing
```

Ownership class:

```text
sensitive mutating admin tool
not safe for automatic deploy
must be reconstructed with fake/test values and runtime-only secrets
```

### telegram_bot_simple.py

Role:

```text
large production Ghost Access control plane
```

Observed structure:

```text
top-level functions: 346
total function/method nodes: 351
classes: 6
top-level sync functions: 269
top-level async functions: 77
database imports: 75
command/handler functions: 41
subprocess usage: subprocess.run
```

Top-level classes:

```text
PlanConfig
DeviceSlotAddonConfig
RateLimitState
CachedPayload
XrayError
_FallbackBridge
```

Main areas:

```text
Telegram command handlers
payment providers and webhooks
device slot lifecycle
subscription delivery
Xray profile/link generation
runtime Xray user management
admin menus and admin actions
abuse/rate-limit checks
health and HTTP handlers
background reconciliation loops
```

Ownership class:

```text
mixed UI + billing + provisioning + runtime admin control plane
not safe as one deployable blob
should be split before repo promotion
```

## Runtime Dependency Map

Environment variable names observed in redacted structure:

```text
ADMIN_USER_IDS
BASE_URL
BOT_BRAND
BOT_SINGLETON_LOCK_FILE
BOT_USERNAME
CARDLINK_API_TOKEN
CARDLINK_SHOP_ID
CARDLINK_WEBHOOK_PORT
DEVICE_ACTIVITY_STATE_FILE
DEVICE_ACTIVITY_SYNC_INTERVAL_SECONDS
DEVICE_ACTIVITY_SYNC_SCRIPT
GHOST_ACCESS_DB_PATH
PAYMENT_QUEUE_ALERT_THRESHOLD
PROMETHEUS_ENABLED
PROMETHEUS_PORT
SUBSCRIPTION_BASE_URL
SUBSCRIPTION_HTTP_PORT
TELEGRAM_BOT_TOKEN
TELEGRAM_POLLING_ENABLED
WEB_ACCESS_BASE_URL
XRAY_CLIENT_MANAGER
XRAY_CONFIG_PATH
XRAY_RELOAD_DEBOUNCE_SECONDS
XRAY_RUNTIME_API_SERVER
XRAY_RUNTIME_CMD_TIMEOUT_SECONDS
XRAY_RUNTIME_CONFIG_PATH
XRAY_RUNTIME_TAGS
XRAY_RUNTIME_USER_MANAGER
YOOKASSA_RETURN_URL
YOOKASSA_SECRET_KEY
YOOKASSA_SHOP_ID
YOOKASSA_WEBHOOK_SECRET
YOOMONEY_API_TOKEN
YOOMONEY_RECEIVER
```

Transport/profile configuration names observed:

```text
VPN_SERVER
VPN_PORT
PROFILE_VPN_SERVER
SECONDARY_VPN_PORT
SPB_PROFILE_SERVER
SPB_PROFILE_PRIMARY_PORT
SPB_REALITY_PUBLIC_KEY
SPB_REALITY_SHORT_ID
NL_BETA_VPN_SERVER
NL_BETA_VPN_PORT
NL_BETA_REALITY_PUBLIC_KEY
NL_BETA_REALITY_SHORT_ID
REALITY_PUBLIC_KEY
ENABLE_SECONDARY_REALITY_FALLBACK
ENABLE_XHTTP_FALLBACK
ENABLE_ANDROID_STEALTH_NL_BETA_FALLBACK
EXPOSE_FALLBACK_TRANSPORTS
```

These are names only. Values must stay in runtime secrets, not repo source.

## Mutation Surface

These areas can change production state:

```text
create/update/revoke device records
create/update payment records
claim offline subscriptions
grant referral bonuses
delete user account
create/redeem/delete promo codes
call runtime Xray user manager
schedule Xray reload
run operator/admin commands
write subscription access records
process payment webhooks
```

This means the Ghost Access bot cannot be treated as a read-only diagnostic
component.

## Recommended Source Split

Before promotion into deployable source, split the large bot into smaller owned
modules:

```text
ghost-access/
  bot_app.py                  Telegram app wiring and command registration
  bot_handlers.py             user/admin command handlers
  menus.py                    menu builders and text rendering
  payments.py                 YooKassa/YooMoney/Cardlink integration
  devices.py                  device lifecycle and naming
  subscriptions.py            subscription URLs/payloads/access portal
  transports.py               VLESS/XHTTP/fallback profile construction
  runtime_xray.py             Xray runtime manager wrapper
  health.py                   HTTP health, diagnostics, background checks
  abuse.py                    rate-limit and suspicious-user checks
  offline_issue.py            offline provisioning, no raw secrets
  config.py                   typed env parsing, no values committed
```

## Minimum Tests Before Promotion

Use fake values only:

```text
subscription URL builder redacts/uses placeholders
Telegram-only degraded delivery policy does not mark VPN transport broken
payment webhook idempotency through is_webhook_processed/record_webhook_processed
device limit with extra slot add-on
offline claim token generation stores no raw VPN links in fixtures
runtime_xray wrapper dry-run blocks subprocess mutation by default
config parser requires secrets from environment, never defaults to real values
```

## Recommendation

Do not promote the redacted files directly.

Next safe step:

```text
1. create clean skeleton modules from the ownership split;
2. add tests with fake config values;
3. keep production env values only on NL/runtime secret storage;
4. only then compare reconstructed source behavior against redacted structure.
```
