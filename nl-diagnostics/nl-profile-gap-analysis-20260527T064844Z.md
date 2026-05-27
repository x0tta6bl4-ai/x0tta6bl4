# NL Profile Gap Analysis

profile: `/mnt/projects/nl-diagnostics/nl-server-profile/20260527T064844Z`

## Summary

```json
{
  "local_name_drift": 7,
  "missing_local_source": 12,
  "redacted_review_only": 2,
  "same_hash_elsewhere": 5,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

## Findings

### Missing Or Drifted Current Runtime Sources

| Component | Remote path | Status | Local candidates |
|---|---|---|---|
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_delivery_canary.py` | `local_name_drift` | backup-20260410-090811/scripts/run_vpn_delivery_canary.py |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py` | `local_name_drift` | backup-20260410-090811/scripts/run_vpn_service_access_agent.py |
| ghost-access | `/opt/ghost-access-bot/current/scripts/sync_spb_standalone_clients.py` | `missing_local_source` | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py` | `missing_local_source` | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/xray_runtime_user_manager.py` | `local_name_drift` | backup-20260410-090811/scripts/xray_runtime_user_manager.py |
| ghost-access | `/opt/ghost-access-bot/current/scripts/xui_client_manager.py` | `local_name_drift` | backup-20260410-090811/scripts/xui_client_manager.py |
| ghost-vpn | `/etc/ghost-access/nl-beta-2443.json` | `missing_local_source` | - |
| ghost-vpn | `/mnt/projects/scripts/ghost_tcp_bridge.py` | `missing_local_source` | - |
| ghost-vpn | `/mnt/projects/src/network/ghost_vpn_client.py` | `missing_local_source` | - |
| ghost-vpn | `/mnt/projects/src/network/ghost_vpn_protocol.py` | `local_name_drift` | services/nl-server/ghost-vpn/ghost_vpn_protocol.py |
| ghost-vpn | `/mnt/projects/src/network/ghost_vpn_server.py` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/apply_config_auto.py` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/auto_monitor.py` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/full_stealth_config.py` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/health_check.sh` | `local_name_drift` | scripts/health_check.sh, backup-20260410-090811/scripts/health_check.sh |
| mesh | `/opt/x0tta6bl4-mesh/scripts/listener_loss_signal.py` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/publish_client_profile_hint.py` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/rotation_timer.sh` | `missing_local_source` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py` | `local_name_drift` | services/nl-server/mesh-runtime/vps_build_runtime_state.py |

### Server Runtime Artifacts

These should stay as server runtime artifacts, not normal repo source files.

| Component | Remote path |
|---|---|
| xui | `/etc/x-ui/x-ui.db` |
| xui | `/usr/local/x-ui/bin/config.json` |
| xui | `/usr/local/x-ui/bin/xray-linux-amd64.real` |
| xui | `/usr/local/x-ui/x-ui` |

### Redacted Review Only

These have sanitized local review copies, but raw source is not stored locally and the redacted files are not deployable.

| Component | Remote path | Redacted local copy |
|---|---|---|
| ghost-access | `/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py` | `services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py` |
| ghost-access | `/opt/ghost-access-bot/current/telegram_bot_simple.py` | `services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py` |

### Server Backup Artifacts

These are backup copies on NL. They are useful for forensic history but should not drive current repo reconciliation.

| Component | Remote path |
|---|---|
| ghost-access | `/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py.bak-20260501T084846Z` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py.bak-20260425T100742Z` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py.bak-20260429T180618Z` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py.bak-20260425T105720Z` |

## Full Artifact Table

| Component | Remote path | Status | Local matches | Local drifts |
|---|---|---|---|---|
| ghost-access | `/opt/ghost-access-bot/current/scripts/check_bot_user_chains.py` | `same_hash_elsewhere` | `services/nl-server/ghost-access/check_bot_user_chains.py` | `backup-20260410-090811/scripts/check_bot_user_chains.py` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py` | `redacted_review_only` | `services/nl-server/redacted/ghost-access/issue_offline_subscription.redacted.py` | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/issue_offline_subscription.py.bak-20260501T084846Z` | `server_backup_only` | - | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_telegram_bot_simple.sh` | `same_hash_elsewhere` | `backup-20260410-090811/scripts/run_telegram_bot_simple.sh` | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_delivery_canary.py` | `local_name_drift` | - | `backup-20260410-090811/scripts/run_vpn_delivery_canary.py` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py` | `local_name_drift` | - | `backup-20260410-090811/scripts/run_vpn_service_access_agent.py` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py.bak-20260425T100742Z` | `server_backup_only` | - | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/run_vpn_service_access_agent.py.bak-20260429T180618Z` | `server_backup_only` | - | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/sync_spb_standalone_clients.py` | `missing_local_source` | - | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py` | `missing_local_source` | - | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/sync_xray_device_activity.py.bak-20260425T105720Z` | `server_backup_only` | - | - |
| ghost-access | `/opt/ghost-access-bot/current/scripts/xray_runtime_user_manager.py` | `local_name_drift` | - | `backup-20260410-090811/scripts/xray_runtime_user_manager.py` |
| ghost-access | `/opt/ghost-access-bot/current/scripts/xui_client_manager.py` | `local_name_drift` | - | `backup-20260410-090811/scripts/xui_client_manager.py` |
| ghost-access | `/opt/ghost-access-bot/current/telegram_bot_simple.py` | `redacted_review_only` | `services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py` | - |
| ghost-vpn | `/etc/ghost-access/nl-beta-2443.json` | `missing_local_source` | - | - |
| ghost-vpn | `/mnt/projects/scripts/ghost_tcp_bridge.py` | `missing_local_source` | - | - |
| ghost-vpn | `/mnt/projects/src/network/ghost_vpn_client.py` | `missing_local_source` | - | - |
| ghost-vpn | `/mnt/projects/src/network/ghost_vpn_protocol.py` | `local_name_drift` | - | `services/nl-server/ghost-vpn/ghost_vpn_protocol.py` |
| ghost-vpn | `/mnt/projects/src/network/ghost_vpn_server.py` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/apply_config_auto.py` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/auto_monitor.py` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/build_runtime_state.py` | `same_hash_elsewhere` | `services/nl-server/mesh-runtime/build_runtime_state.py` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/full_stealth_config.py` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/health_check.sh` | `local_name_drift` | - | `scripts/health_check.sh`, `backup-20260410-090811/scripts/health_check.sh` |
| mesh | `/opt/x0tta6bl4-mesh/scripts/listener_loss_signal.py` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/monitor.py` | `same_hash_elsewhere` | `services/nl-server/mesh-runtime/monitor.py` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/profile_status_api.py` | `same_hash_elsewhere` | `services/nl-server/mesh-runtime/profile_status_api.py` | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/publish_client_profile_hint.py` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/rotation_timer.sh` | `missing_local_source` | - | - |
| mesh | `/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py` | `local_name_drift` | - | `services/nl-server/mesh-runtime/vps_build_runtime_state.py` |
| xui | `/etc/x-ui/x-ui.db` | `server_runtime_artifact` | - | - |
| xui | `/usr/local/x-ui/bin/config.json` | `server_runtime_artifact` | - | - |
| xui | `/usr/local/x-ui/bin/xray-linux-amd64.real` | `server_runtime_artifact` | - | - |
| xui | `/usr/local/x-ui/x-ui` | `server_runtime_artifact` | - | - |

## Recommended Next Work

1. Create a repo-owned `nl-server-profile` source area for scripts that are current on NL but missing locally.
2. Do not copy secrets or full databases; only bring source code/config templates with explicit redaction.
3. Treat `x-ui` binaries, `/etc/x-ui/x-ui.db`, and generated `/usr/local/x-ui/bin/config.json` as runtime artifacts.
4. Replace backup-only entries with a short retention note instead of trying to reconcile them.
5. Reconstruct `redacted_review_only` files into clean deployable source before considering them repo-owned.
6. Before any future NL write, require: fresh read-only profile, x-ui db/config backup plan, rollback command, and explicit operator approval.

No NL writes were performed by this analysis.
