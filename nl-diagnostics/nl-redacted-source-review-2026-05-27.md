# NL Redacted Source Review, 2026-05-27

## Status

Two previously blocked Ghost Access files were read from NL in read-only mode and
saved only as redacted local review copies.

```text
NL writes: 0
raw source saved locally: false
redacted copies deployable: false
```

## Inputs

Blocked by the original quarantine intake:

```text
/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py
/opt/ghost-access-bot/current/telegram_bot_simple.py
```

Reason:

```text
vpn_uri pattern detected
```

## Tool

```text
services/nl-server/tools/pull_candidate_redacted.py
sha256: 8220573a8c6b21f7ed0c7c087222e94990fb548c301cffd9714e9f1c308a82fb
```

The tool:

```text
reads raw content into memory only
redacts VPN URIs, UUIDs, key assignments, token assignments, and private-key blocks
writes only redacted files and metadata
blocks output if post-scan still finds sensitive patterns
```

## Outputs

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
```

Hashes:

```text
issue_offline_subscription.redacted.py
  raw_sha256:      aa358dd59d03b1a5130bf06fc88ab9c45f80d057c8ce6ec5b1e0f8f636ae0552
  redacted_sha256: 22490b4f33889f11d05396e147734c43e44ed188af5c0e385c8c74b81135a8f6

telegram_bot_simple.redacted.py
  raw_sha256:      b593ddd82b3542e02e8a6fc17b558d957d780326ab86b5f7bd203d8d1d5b2f93
  redacted_sha256: 775cd3e2381735a6611db2390a43e2cd658a5d23f522a9ff3d748cc417505072
```

Redaction counts:

```json
{
  "issue_offline_subscription.py": {
    "private_key_assignment": 0,
    "private_key_block": 0,
    "public_key_assignment": 0,
    "short_id_assignment": 0,
    "subscription_url_assignment": 0,
    "token_assignment": 0,
    "uuid": 0,
    "vpn_uri": 2
  },
  "telegram_bot_simple.py": {
    "private_key_assignment": 0,
    "private_key_block": 0,
    "public_key_assignment": 0,
    "short_id_assignment": 0,
    "subscription_url_assignment": 0,
    "token_assignment": 0,
    "uuid": 0,
    "vpn_uri": 4
  }
}
```

## Validation

```text
post-redaction secret scan: ok
python syntax check: ok
metadata JSON check: ok
raw source saved locally: false
deployable: false
```

Structured summary:

```text
issue_offline_subscription.redacted.py:
  functions: 11
  classes: 0
  key functions:
    generate_claim_code
    generate_subscription_token
    ensure_table
    run_xray
    show_profile
    build_vless_link
    build_xhttp_link
    subscription_base_url
    web_access_base_url
    parse_args
    main

telegram_bot_simple.redacted.py:
  functions: 351
  classes: 6
  key classes:
    PlanConfig
    DeviceSlotAddonConfig
    RateLimitState
    CachedPayload
    XrayError
    _FallbackBridge
  key areas:
    payment providers
    device slots
    invite/account/admin menus
    xray profile/link generation
    runtime/admin checks
    subscription delivery
```

## Findings

`issue_offline_subscription.py` is a mutating/offline provisioning helper:

```text
uses sqlite
generates claim/subscription tokens
can run xray/profile commands
builds VLESS/XHTTP links
```

`telegram_bot_simple.py` is not just a bot UI file. It is a large production
control plane:

```text
payment handling
device/account lifecycle
subscription delivery
Xray/Ghost profile generation
admin runtime actions
```

## Recommendation

Do not promote these redacted files as deployable source.

Next safe local work:

```text
1. create a bot/control-plane ownership map from the redacted structure;
2. separate deployable source reconstruction from secret-bearing runtime config;
3. extract tests around subscription delivery semantics using fake placeholders;
4. keep raw production values only on NL/runtime secrets, never in repo.
```
