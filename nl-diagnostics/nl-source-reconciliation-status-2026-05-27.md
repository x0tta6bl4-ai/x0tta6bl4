# NL Source Reconciliation Status

Status: current NL source reconciliation is locally closed for the latest
read-only profile.

Profile:

```text
nl-diagnostics/nl-server-profile/20260527T173222Z
```

Current gap summary:

```json
{
  "accepted_local_delta": 2,
  "redacted_review_only": 2,
  "redacted_template_only": 1,
  "same_hash_elsewhere": 21,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

## Meaning

- `missing_local_source=0`: no current NL source file is now silently absent
  from local reconciliation.
- `local_name_drift=0`: no same-name drift is left unexplained.
- `same_hash_elsewhere=21`: 21 current NL artifacts have exact local copies.
- `accepted_local_delta=2`: 2 files intentionally differ locally and are not
  deployable to NL.
- `redacted_review_only=2`: sensitive Ghost Access sources are retained only as
  sanitized review copies.
- `redacted_template_only=1`: `/etc/ghost-access/nl-beta-2443.json` is
  represented by a safe template plus metadata; raw production values were not
  saved.

## SPB Status

SPB standalone Xray is disabled and not used in the current VPN path.

`services/nl-server/ghost-access/sync_spb_standalone_clients.py` is retained
only because it exists on NL and is needed for source reconciliation. It remains
inactive, class C, and non-deployable.

## Accepted Local Deltas

```text
services/nl-server/mesh-runtime/vps_build_runtime_state.py
services/nl-server/ghost-vpn/ghost_vpn_protocol.py
```

These differ from current NL intentionally:

- `vps_build_runtime_state.py`: local policy treats Telegram media degradation
  with healthy transport as advisory/observe, aligns public ports with current
  NL, and prefers `/usr/local/x-ui/bin/config.json`.
- `ghost_vpn_protocol.py`: local import fallback keeps workspace tests working.

Neither delta is deployable to NL without a separate review.

## Checks

Latest checks passed:

```text
python3 -m unittest discover -s services/nl-server/tests -p 'test_*.py'
python3 nl-diagnostics/test_analyze_nl_profile_gaps.py
python3 nl-diagnostics/test_classify_vpn_snapshot.py
python3 nl-diagnostics/test_build_provider_incident_packet.py
python3 nl-diagnostics/test_profile_switch_policy.py
python3 services/nl-server/tools/validate_preflight_readiness.py
scoped secret scan over NL/VPN-touched paths
```

No NL or SPB writes were performed.
