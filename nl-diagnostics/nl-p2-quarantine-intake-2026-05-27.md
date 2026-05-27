# NL P2 Quarantine Intake, 2026-05-27

## Status

NL remained read-only from the server side.

Remote action:

```text
ssh nl cat <source file>
```

No server mutation was performed.

Local intake batch:

```text
services/nl-server/.quarantine/incoming/20260527T060043Z
```

Result:

```text
accepted: 10
blocked: 2
```

Blocked files were not saved during automatic quarantine intake:

```text
/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py
/opt/ghost-access-bot/current/telegram_bot_simple.py
```

Reason:

```text
vpn_uri pattern detected
```

These two require redaction workflow, not automatic intake.

Follow-up redaction status:

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
nl-diagnostics/nl-redacted-source-review-2026-05-27.md
```

Raw source was not saved locally. The redacted copies are for review only and
are not deployable.

## Validation

Checks run locally:

```text
python3 -m py_compile services/nl-server/.quarantine/incoming/20260527T060043Z/mesh-runtime/*.py
python3 -m py_compile services/nl-server/.quarantine/incoming/20260527T060043Z/ghost-access/*.py
bash -n services/nl-server/.quarantine/incoming/20260527T060043Z/mesh-runtime/rotation_timer.sh
bash -n services/nl-server/.quarantine/incoming/20260527T060043Z/ghost-access/run_telegram_bot_simple.sh
```

Additional scan note:

```text
run_telegram_bot_simple.sh contains TELEGRAM_BOT_TOKEN presence check, not a token value.
```

## Accepted P2 Files

```text
mesh-runtime/apply_config_auto.py             10405 bytes
mesh-runtime/auto_monitor.py                  3928 bytes
mesh-runtime/full_stealth_config.py           3946 bytes
mesh-runtime/monitor.py                       3692 bytes
mesh-runtime/profile_status_api.py            2829 bytes
mesh-runtime/rotation_timer.sh                1624 bytes
mesh-runtime/vps_build_runtime_state.py      13665 bytes
ghost-access/check_bot_user_chains.py         5673 bytes
ghost-access/run_telegram_bot_simple.sh        417 bytes
ghost-access/sync_spb_standalone_clients.py   3414 bytes
```

## Hash Comparison Against Local Workspace

```text
ghost-access/check_bot_user_chains.py
  NL:         62ffaca72e3e093714758add99ec259708eecfe754f8e6de1a961ea3ac31135b
  old backup: 39b9c98ee83c0ae7ec3c54f4e5e1e813a225f75d6ffd5641a192ee6443f3c68a

ghost-access/run_telegram_bot_simple.sh
  NL:         e61c7b1ef00d990391c3139d5fd0e7db2c8c8896cb36723980969a6ff9684a40
  old backup: e61c7b1ef00d990391c3139d5fd0e7db2c8c8896cb36723980969a6ff9684a40
```

The pulled mesh-runtime P2 files were missing under local `scripts/`:

```text
apply_config_auto.py
auto_monitor.py
full_stealth_config.py
monitor.py
profile_status_api.py
rotation_timer.sh
vps_build_runtime_state.py
```

## Key Findings

### 1. Runtime-state generator confirms the `degraded` semantic bug

`vps_build_runtime_state.py` maps Telegram media degradation to general runtime
degradation:

```text
telegram_media_status in degraded/unhealthy -> mode=degraded, action=observe
```

This confirms the operational symptom seen in the snapshot:

```text
transport healthy
Telegram media slow
overall runtime mode degraded
```

Future source fix should keep transport health separate:

```text
transport healthy + telegram degraded -> overall advisory, action observe
```

### 2. Runtime-state generator has stale production assumptions

The pulled source uses:

```text
XUI_CONFIG = /usr/local/etc/xray/config.json
AUXILIARY_PORTS = [9443, 8388, 2096, 628]
PRIMARY_PORT = 443
```

Current NL evidence says real x-ui config is under:

```text
/usr/local/x-ui/bin/config.json
```

and real x-ui Reality listeners are:

```text
443
2083
39829
```

This means local runtime-state generation can miss real NL paths or keep checking
old ports. That is a likely source of misleading degraded/advisory signals.

### 3. Several P2 scripts are mutating config tools

These are not safe observability scripts:

```text
apply_config_auto.py
full_stealth_config.py
rotation_timer.sh
sync_spb_standalone_clients.py
```

Observed behavior:

```text
write /usr/local/x-ui/bin/config.json
send signal to xray
restart remote xray on SPB
write route/rotation state
```

They should stay out of any automatic health path until they have:

```text
dry-run mode
backup path
rollback command
explicit mutation flag
maintenance window
```

### 4. Observability candidates are separable

These files are closer to observability/control plane:

```text
vps_build_runtime_state.py
profile_status_api.py
monitor.py
auto_monitor.py
check_bot_user_chains.py
```

Even these write local state/logs on NL when run, so they are not "read-only" in
the strict diagnostic sense. They can become source-of-truth after review, but
they should not be executed from local diagnostics.

## Recommendation

Promotion order:

```text
1. vps_build_runtime_state.py into reviewed source, with tests for status semantics.
2. profile_status_api.py and monitor.py after confirming metrics paths.
3. auto_monitor.py only after alert semantics are fixed.
4. mutating config scripts only after backup/rollback gates.
5. blocked files only through redacted review copies, not automatic intake or deploy.
```

No NL deploy is recommended yet.

## Redacted Follow-Up

The two blocked files were later read again from NL in read-only mode and saved
only as redacted local review copies:

```text
services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py
services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py
```

Validation result:

```text
post-redaction secret scan: ok
python syntax check: ok
metadata JSON check: ok
deployable: false
```

The review conclusion did not change their promotion class. They remain
sensitive control-plane source and must be reconstructed into clean source plus
runtime-only secrets before any future deploy.
