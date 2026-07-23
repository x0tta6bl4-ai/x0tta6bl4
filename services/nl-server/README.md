# NL Server Source Area

Status: local-only planning area. Nothing here is deployed to NL.

NL is currently read-only. Do not copy files from this directory to NL, restart
services, edit `x-ui`, or change cron/systemd without explicit operator
approval.

## Purpose

This directory separates the real NL server profile from older local templates.
It is the future home for reviewed source that currently exists only on NL.

Current evidence:

```text
nl-diagnostics/nl-server-profile/20260527T173222Z
nl-diagnostics/nl-profile-gap-analysis-20260527T173222Z.md
nl-diagnostics/nl-source-reconciliation-plan-2026-05-27.md
nl-diagnostics/nl-source-reconciliation-status-2026-05-27.md
nl-diagnostics/nl-vpn-improvement-execution-plan-2026-05-27.md
nl-diagnostics/nl-remaining-source-gap-risk-2026-05-27.md
nl-diagnostics/nl-spb-integration-status-2026-05-27.md
```

## Source Policy

Allowed here:

- reviewed Python/Bash source copied from NL only after secret review;
- templates with fake/example values only;
- systemd documentation and sanitized unit shapes;
- tests that run locally without touching NL.

Not allowed here:

- x-ui database dumps;
- generated `/usr/local/x-ui/bin/config.json`;
- private/public keys, UUIDs, short IDs, bot tokens, subscription URLs;
- production `.env` files;
- x-ui binaries or Xray binaries.

## Layout

```text
services/nl-server/
  manifest.json
  tools/
  .quarantine/
  systemd/
  mesh-runtime/
  ghost-access/
  ghost-vpn/
  templates/
```

## Current Rule

Current promotion state:

```text
promoted source files: 22
deployable_to_nl: false
latest gap summary: accepted_local_delta=5, redacted_template_only=1, same_hash_elsewhere=18, missing_local_source=0, local_name_drift=0
latest added tests: services/nl-server/tests/test_activity_sync_and_tcp_bridge.py, services/nl-server/tests/test_ghost_vpn_runtime_source.py, services/nl-server/tests/test_auto_monitor_source.py, services/nl-server/tests/test_apply_config_auto_source.py, services/nl-server/tests/test_full_stealth_config_source.py, services/nl-server/tests/test_rotation_timer_source.py, services/nl-server/tests/test_spb_standalone_sync_source.py, services/nl-server/tests/test_current_nl_runtime_source.py
redacted templates: services/nl-server/templates/nl-beta-2443.example.json, services/nl-server/templates/nl-beta-2443.example.json.meta.json
```

Before any file becomes deployable source:

1. Pull/read it into a quarantine location, not directly here.
2. Run secret scan and manual review.
3. Add or update local tests.
4. Record its NL source hash in `manifest.json`.
5. Require explicit approval before any NL write.

The helper for step 1 is dry-run by default:

```bash
python3 services/nl-server/tools/pull_candidate_readonly.py --priority P1
```

Only with `--pull` does it read files from NL, and accepted files stay under the
git-ignored `.quarantine/incoming/` tree.

## Permanently Decommissioned SPB Path

SPB standalone Xray (`195.58.48.193`) is permanently decommissioned and removed from the active VPN architecture by operator directive.
`ghost-access/sync_spb_standalone_clients.py` is retained only as legacy code for historical reference. No traffic or client sync is routed to SPB.
