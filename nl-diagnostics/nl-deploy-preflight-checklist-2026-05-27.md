# NL Deploy Preflight Checklist, 2026-05-27

## Status

This is a local checklist for a future maintenance window.

```text
NL write permission now: false
execute these commands now: no
```

Nothing in this document was executed on NL while the server is read-only.

## Scope Of First Future Deploy

Allowed future target, after explicit approval only:

```text
/opt/x0tta6bl4-mesh/scripts/health_check_readonly.sh
/opt/x0tta6bl4-mesh/scripts/health_action_policy.py
/opt/x0tta6bl4-mesh/scripts/health_heal_xui.sh
```

Not included in first deploy:

```text
x-ui db edits
x-ui generated config edits
Ghost VPN server/client route or iptables changes
Telegram bot files
subscription/offline issue files
systemd timer changes
cron changes
```

## Gate 0: Operator Approval

Required explicit operator sentence before any NL write:

```text
approve NL write for health shell split only
```

Without that exact approval, stay local/read-only.

## Gate 1: Fresh Read-Only Evidence

Run locally:

```bash
bash nl-diagnostics/collect_vpn_readonly_snapshot.sh
bash nl-diagnostics/collect_nl_server_profile_readonly.sh
python3 nl-diagnostics/classify_vpn_snapshot.py nl-diagnostics/snapshots/latest
```

Expected:

```text
mutation_allowed: false
nl_mutation_allowed: false
transport_status: healthy or advisory
provider_status: not provider_outage
systemctl --failed: 0 or explained
```

Stop if:

```text
provider_outage
high steal/load/disk await
missing primary listener without a maintenance window
snapshot failed
profile collection failed
```

## Gate 2: Source Checks

Run locally:

```bash
python3 services/nl-server/tests/test_vps_build_runtime_state.py
python3 services/nl-server/tests/test_profile_status_and_ghost_protocol.py
python3 services/nl-server/tests/test_health_action_policy.py
python3 services/nl-server/tools/validate_preflight_readiness.py
python3 nl-diagnostics/test_classify_vpn_snapshot.py
python3 -m json.tool services/nl-server/manifest.json
bash -n services/nl-server/mesh-runtime/health_check_readonly.sh services/nl-server/mesh-runtime/health_heal_xui.sh
```

Expected:

```text
all tests pass
manifest JSON valid
shell syntax OK
secret scan has no real values
preflight validator returns ok=true and deploy_status=local_ready_but_deploy_blocked
```

## Gate 3: Hash Diff Against Fresh NL

Compare local intended files against fresh profile hashes:

```text
services/nl-server/mesh-runtime/health_check_readonly.sh
services/nl-server/mesh-runtime/health_action_policy.py
services/nl-server/mesh-runtime/health_heal_xui.sh
```

Expected:

```text
new files or intentional diff only
no replacement of existing health_check.sh unless explicitly approved
```

The first deploy should add new files, not replace the existing mutating
`health_check.sh`.

## Gate 4: Backup Commands To Prepare

Prepare these commands for the future maintenance window.

Do not run while NL is read-only.

```bash
ssh nl 'set -euo pipefail
ts=$(date -u +%Y%m%dT%H%M%SZ)
sudo install -d -m 0700 /root/nl-vpn-backups/"$ts"
sudo cp -a /opt/x0tta6bl4-mesh/scripts /root/nl-vpn-backups/"$ts"/mesh-scripts
sudo cp -a /opt/x0tta6bl4-mesh/state /root/nl-vpn-backups/"$ts"/mesh-state
sudo cp -a /etc/systemd/system /root/nl-vpn-backups/"$ts"/systemd-system
sudo sqlite3 /etc/x-ui/x-ui.db ".backup /root/nl-vpn-backups/$ts/x-ui.db"
sudo cp -a /usr/local/x-ui/bin/config.json /root/nl-vpn-backups/"$ts"/x-ui-bin-config.json
sudo sha256sum /root/nl-vpn-backups/"$ts"/x-ui.db /root/nl-vpn-backups/"$ts"/x-ui-bin-config.json > /root/nl-vpn-backups/"$ts"/SHA256SUMS
echo /root/nl-vpn-backups/"$ts"'
```

Expected:

```text
prints backup directory path
backup directory contains mesh scripts, state, x-ui db backup, x-ui generated config
```

## Gate 5: Staged Copy Commands To Prepare

Preferred first write target:

```text
/opt/x0tta6bl4-mesh/scripts/.staged-<timestamp>/
```

Prepare, do not run now:

```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
ssh nl "sudo install -d -m 0750 /opt/x0tta6bl4-mesh/scripts/.staged-$ts"
scp services/nl-server/mesh-runtime/health_check_readonly.sh nl:/tmp/health_check_readonly.sh
scp services/nl-server/mesh-runtime/health_action_policy.py nl:/tmp/health_action_policy.py
scp services/nl-server/mesh-runtime/health_heal_xui.sh nl:/tmp/health_heal_xui.sh
ssh nl "sudo install -m 0750 /tmp/health_check_readonly.sh /opt/x0tta6bl4-mesh/scripts/.staged-$ts/health_check_readonly.sh"
ssh nl "sudo install -m 0640 /tmp/health_action_policy.py /opt/x0tta6bl4-mesh/scripts/.staged-$ts/health_action_policy.py"
ssh nl "sudo install -m 0750 /tmp/health_heal_xui.sh /opt/x0tta6bl4-mesh/scripts/.staged-$ts/health_heal_xui.sh"
ssh nl "sudo rm -f /tmp/health_check_readonly.sh /tmp/health_action_policy.py /tmp/health_heal_xui.sh"
```

Expected:

```text
files are staged only
no systemd reload
no service restart
existing health_check.sh unchanged
```

## Gate 6: Staged Validation Commands To Prepare

Prepare, do not run now:

```bash
ssh nl 'set -euo pipefail
stage=$(find /opt/x0tta6bl4-mesh/scripts -maxdepth 1 -type d -name ".staged-*" | sort | tail -n 1)
bash -n "$stage/health_check_readonly.sh" "$stage/health_heal_xui.sh"
python3 -m py_compile "$stage/health_action_policy.py"
STATE_FILE=/opt/x0tta6bl4-mesh/state/runtime-state.json "$stage/health_check_readonly.sh"
STATE_FILE=/opt/x0tta6bl4-mesh/state/runtime-state.json COOLDOWN_FILE=/opt/x0tta6bl4-mesh/state/restart-cooldown.json "$stage/health_heal_xui.sh"'
```

Expected:

```text
readonly health prints state
heal wrapper prints blocked_mutation_flag or observe
no x-ui restart
no cooldown write unless execute flag is set
```

## Gate 7: Promotion Commands To Prepare

Only after staged validation:

```bash
ssh nl 'set -euo pipefail
stage=$(find /opt/x0tta6bl4-mesh/scripts -maxdepth 1 -type d -name ".staged-*" | sort | tail -n 1)
sudo install -m 0750 "$stage/health_check_readonly.sh" /opt/x0tta6bl4-mesh/scripts/health_check_readonly.sh
sudo install -m 0640 "$stage/health_action_policy.py" /opt/x0tta6bl4-mesh/scripts/health_action_policy.py
sudo install -m 0750 "$stage/health_heal_xui.sh" /opt/x0tta6bl4-mesh/scripts/health_heal_xui.sh'
```

Expected:

```text
new files installed
old health_check.sh still unchanged
no service restart
```

## Gate 8: Post-Write Read-Only Verification

Run locally after a future approved write:

```bash
bash nl-diagnostics/collect_vpn_readonly_snapshot.sh
bash nl-diagnostics/collect_nl_server_profile_readonly.sh
python3 nl-diagnostics/classify_vpn_snapshot.py nl-diagnostics/snapshots/latest
```

Expected:

```text
transport still healthy/advisory
systemctl --failed unchanged
x-ui active
listeners 443/2083/39829 present
new file hashes match local manifest
```

## Rollback Commands To Prepare

If new files cause trouble, remove only the new files:

```bash
ssh nl 'sudo rm -f \
  /opt/x0tta6bl4-mesh/scripts/health_check_readonly.sh \
  /opt/x0tta6bl4-mesh/scripts/health_action_policy.py \
  /opt/x0tta6bl4-mesh/scripts/health_heal_xui.sh'
```

If existing files were changed by mistake, restore from backup:

```bash
ssh nl 'set -euo pipefail
backup_dir=/root/nl-vpn-backups/<timestamp>
sudo rsync -a --delete "$backup_dir/mesh-scripts/" /opt/x0tta6bl4-mesh/scripts/
sudo rsync -a --delete "$backup_dir/mesh-state/" /opt/x0tta6bl4-mesh/state/'
```

Only restore x-ui DB/config if the deploy actually touched them. This first
future deploy must not touch them.

## Hard Stop Conditions

Stop and do not deploy if any of these are true:

```text
fresh profile cannot be collected
fresh snapshot cannot be classified
provider_status is provider_outage
systemctl --failed is not understood
x-ui db backup command fails
secret scan finds real keys, tokens, UUID links, or VPN URIs
local tests fail
operator approval is missing
```
