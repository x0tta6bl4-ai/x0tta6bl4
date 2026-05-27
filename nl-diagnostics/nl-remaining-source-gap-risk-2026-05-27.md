# NL Remaining Source Gap Risk, 2026-05-27

## Status

NL remained read-only.

No deploy, no restart, no `scp` to NL, no x-ui DB/config write, no systemd
change.

Latest source gap summary:

```json
{
  "local_name_drift": 7,
  "missing_local_source": 2,
  "redacted_review_only": 2,
  "same_hash_elsewhere": 15,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

## Remaining Missing Items

| Remote path | Risk class | Why not promoted directly |
|---|---:|---|
| `/etc/ghost-access/nl-beta-2443.json` | D | Redacted template now exists at `services/nl-server/templates/nl-beta-2443.example.json`; raw config remains intentionally unsaved. |
| `/opt/x0tta6bl4-mesh/scripts/apply_config_auto.py` | C | Local-only source restored at `services/nl-server/mesh-runtime/apply_config_auto.py`; not deployable because it writes `/usr/local/x-ui/bin/config.json` and validates with xray binary. |
| `/opt/x0tta6bl4-mesh/scripts/full_stealth_config.py` | C | Local-only source restored at `services/nl-server/mesh-runtime/full_stealth_config.py`; not deployable because it writes x-ui generated config and rotation metadata. |
| `/opt/x0tta6bl4-mesh/scripts/rotation_timer.sh` | C | Local-only source restored at `services/nl-server/mesh-runtime/rotation_timer.sh`; not deployable because it runs `full_stealth_config.py` and signals Xray with `pkill -USR1`. |
| `/opt/ghost-access-bot/current/scripts/sync_spb_standalone_clients.py` | C/D | Reads UUIDs and pushes SPB config over SSH, then restarts remote `xray`. Needs redaction and remote-mutation gates. |

## Safe Next Work

1. Convert config writers into dry-run-first local source before any deploy use.
2. Keep `sync_spb_standalone_clients.py` in quarantine until UUID handling and remote restart behavior are isolated behind explicit flags.
3. Require fresh read-only NL profile, backup path and rollback command before any future class C run.

## Template Created

```text
services/nl-server/templates/nl-beta-2443.example.json
services/nl-server/tests/test_templates.py
services/nl-server/mesh-runtime/apply_config_auto.py
services/nl-server/tests/test_apply_config_auto_source.py
services/nl-server/mesh-runtime/full_stealth_config.py
services/nl-server/tests/test_full_stealth_config_source.py
services/nl-server/mesh-runtime/rotation_timer.sh
services/nl-server/tests/test_rotation_timer_source.py
```

The template preserves only shape: VLESS Reality on port `2443`, one placeholder
client, three example server names, one placeholder short ID, and direct
outbound. It does not contain production UUIDs, keys, short IDs, VPN URLs, bot
tokens or subscription links.

`apply_config_auto.py` is restored only as reviewed local source. Tests cover
pure config transformations without executing its top-level `/opt` log/backup
side effects and without writing x-ui config.

`full_stealth_config.py` is restored only as reviewed local source. Tests cover
short ID/profile helper behavior and static class-C mutation evidence; they do
not run `apply_full_stealth()`.

`rotation_timer.sh` is restored only as reviewed local source. Tests cover shell
syntax and static class-C mutation evidence; they do not run the rotation or
signal Xray.

No NL writes were performed by this analysis.
