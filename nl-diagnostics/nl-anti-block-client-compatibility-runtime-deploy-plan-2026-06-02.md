# NL Anti-Block Client Compatibility Runtime Deploy Plan - 2026-06-02

## Decision

`CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED`

Dry-run deploy packet. It does not copy files, restart services, reload systemd, enable timers, change x-ui, change nginx, change the bot, or touch fallback services unless explicit apply confirmation is used later.

## Runtime State

| Item | Status |
| --- | --- |
| /transport-usage | HTTP 200 |
| /client-compatibility | HTTP 200 |
| x-ui | active |
| nginx | active |
| telegram-bot-simple.service | active |
| ghost-access-nl-xhttp.service | active |
| ghost-access-nl-https-ws.service | active |
| x0tta6bl4-profile-status-api.service | active |

## Target Files

| Component | Remote Target | Local Exists | Remote Matches Local |
| --- | --- | --- | --- |
| profile_status_api | /opt/x0tta6bl4-mesh/scripts/profile_status_api.py | true | true |
| client_compat_runtime_summary_builder | /opt/x0tta6bl4-mesh/scripts/build_client_compatibility_runtime_summary.py | true | true |
| client_compat_matrix | /var/lib/ghost-access/client-compatibility/matrix.json | true | true |
| client_compat_summary_seed | /var/lib/ghost-access/client-compatibility/latest.json | true | false |
| client_compat_systemd_service | /etc/systemd/system/ghost-access-client-compatibility-summary.service | true | true |
| client_compat_systemd_timer | /etc/systemd/system/ghost-access-client-compatibility-summary.timer | true | true |

## Mutation Policy

- Apply requires `DEPLOY_CLIENT_COMPAT_RUNTIME`.
- Profile status API restart additionally requires `RESTART_PROFILE_STATUS_API`.
- Forbidden restarts: x-ui, nginx, telegram-bot-simple.service, ghost-access-nl-xhttp.service, ghost-access-nl-https-ws.service, ghost-access-nl-xhttp-sync.timer, ghost-access-nl-https-ws-sync.timer
- Allowed units: x0tta6bl4-profile-status-api.service, ghost-access-client-compatibility-summary.service, ghost-access-client-compatibility-summary.timer
