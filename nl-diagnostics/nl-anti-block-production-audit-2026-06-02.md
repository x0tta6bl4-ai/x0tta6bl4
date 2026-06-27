# NL Anti-Block Production Audit - 2026-06-02

## Decision

`PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE`

This audit is generated from current local evidence artifacts. It does not contact NL, restart VPN services, or record client pass/fail evidence.

## Requirements

| Requirement | Status |
| --- | --- |
| fallback_subscriptions | pass |
| multi_transport_same_nl | pass |
| operator_visibility | pass |
| privacy_safe_runtime_evidence | pass |
| reality_legacy_access_alive | pass |
| rollback_dry_run_and_confirm_gates | pass |
| rollback_execution_without_access_loss | pass |
| runtime_evidence | pass |
| user_client_matrix_after_rollout | partial_desktop_pass_mobile_pending |
| client_compatibility_runtime_on_nl | pass |
| production_runtime_deploy_safety | pass |

## Current Blockers

1. record Android Happ/Hiddify client evidence after rollout
2. record one mobile network evidence case
3. record one restricted or work Wi-Fi evidence case
4. collect the 2 safe remote request-packet reports: mobile Happ/Hiddify and restricted/work Wi-Fi
5. rerun preflight/tests after remaining client matrix evidence is added
6. after any new client pass/fail evidence, run refresh_client_evidence_artifacts.py --write before final readiness audit

## Client Matrix

```json
{
  "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
  "passing_real_client_checks": 2,
  "current_evidence_session": {
    "id": "nl-anti-block-2026-06-02",
    "started_at": "2026-06-02T00:00:00Z",
    "required_transport": "reality",
    "required_port": 443,
    "required_for": [
      "android_happ_or_hiddify",
      "mobile_network",
      "restricted_or_work_wifi"
    ],
    "evidence": {
      "android_happ_or_hiddify": false,
      "mobile_network": false,
      "restricted_or_work_wifi": false
    },
    "complete": false
  },
  "missing_requirements": [
    "android_happ_or_hiddify",
    "mobile_network",
    "restricted_or_work_wifi"
  ],
  "next_required_checks": [
    {
      "requirement": "android_happ_or_hiddify",
      "client": "Happ",
      "network_type": "mobile",
      "transport": "reality",
      "port": 443
    },
    {
      "requirement": "restricted_or_work_wifi",
      "client": "any",
      "network_type": "work-wifi",
      "transport": "reality",
      "port": 443
    }
  ]
}
```

## Remote Request Packet

```json
{
  "decision": "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
  "minimum_reports_required": 2,
  "request_count": 2,
  "missing_requirements": [
    "android_happ_or_hiddify",
    "mobile_network",
    "restricted_or_work_wifi"
  ],
  "requests": [
    {
      "request_id": "remote-client-evidence-1",
      "covers_requirements": [
        "android_happ_or_hiddify",
        "mobile_network"
      ],
      "client": "Happ",
      "network_type": "mobile",
      "transport": "reality",
      "port": 443,
      "evidence_session_id": "nl-anti-block-2026-06-02",
      "evidence_session_started_at": "2026-06-02T00:00:00Z",
      "minimum_result_to_close_requirements": "pass",
      "operator_record_pass_command_available": false,
      "operator_record_fail_command_available": false,
      "operator_reply_record_pass_command_available": true,
      "operator_reply_record_fail_command_available": true,
      "safe_reply_options": [
        "pass connected",
        "fail timeout",
        "fail import",
        "fail no-internet"
      ]
    },
    {
      "request_id": "remote-client-evidence-2",
      "covers_requirements": [
        "restricted_or_work_wifi"
      ],
      "client": "any",
      "network_type": "work-wifi",
      "transport": "reality",
      "port": 443,
      "evidence_session_id": "nl-anti-block-2026-06-02",
      "evidence_session_started_at": "2026-06-02T00:00:00Z",
      "minimum_result_to_close_requirements": "pass",
      "operator_record_pass_command_available": false,
      "operator_record_fail_command_available": false,
      "operator_reply_record_pass_command_available": true,
      "operator_reply_record_fail_command_available": true,
      "safe_reply_options": [
        "pass connected",
        "fail timeout",
        "fail import",
        "fail no-internet"
      ]
    }
  ],
  "privacy": {
    "output_privacy_ok": true,
    "raw_subscription_url_stored": false,
    "raw_vpn_uri_stored": false,
    "raw_uuid_stored": false,
    "raw_ip_stored": false,
    "raw_email_stored": false,
    "raw_reporter_identifier_stored": false,
    "raw_telegram_handle_stored": false,
    "raw_phone_stored": false,
    "raw_url_stored": false,
    "raw_screenshot_stored": false,
    "raw_logs_stored": false
  }
}
```

## Runtime Probe

```json
{
  "checked_at": "2026-06-05T09:14:47Z",
  "decision": "NL_CLIENT_COMPAT_RUNTIME_READY",
  "client_compatibility_http_code": 200,
  "client_compatibility_missing_requirements": [
    "android_happ_or_hiddify",
    "mobile_network",
    "restricted_or_work_wifi"
  ],
  "systemd_wiring": {
    "summary_present": true,
    "matrix_present": true,
    "service_unit_present": true,
    "timer_unit_present": true,
    "timer_enabled": "enabled",
    "timer_active": "active"
  },
  "privacy": {
    "output_privacy_ok": true,
    "raw_ssh_config_stored": false,
    "raw_ip_stored": false,
    "raw_subscription_url_stored": false,
    "raw_vpn_uri_stored": false,
    "raw_uuid_stored": false,
    "raw_email_stored": false,
    "raw_phone_stored": false,
    "raw_telegram_handle_stored": false,
    "raw_client_rows_stored": false
  }
}
```

## Live Evidence Summary

```json
{
  "fallback_subscription": {
    "counts": {
      "other": 0,
      "reality": 10,
      "ws": 5,
      "xhttp": 5
    },
    "has_reality": true,
    "has_ws": true,
    "has_xhttp": true,
    "line_count": 20,
    "ports": [
      443,
      2083,
      8443
    ]
  },
  "runtime": {
    "generated_at": "2026-06-01T21:58:20Z",
    "ghost_https_ws_ready": true,
    "ghost_xhttp_ready": true,
    "mode": "advisory",
    "recommended_action": "observe",
    "status_api_privacy_ok": true,
    "status_api_usage_ok": true,
    "subscription_health_status": "healthy"
  },
  "usage_60m": {
    "ghost_https_ws_dataplane_events": 0,
    "ghost_https_ws_nginx_requests": 67,
    "ghost_https_ws_unique_clients": 0,
    "ghost_xhttp_dataplane_events": 0,
    "ghost_xhttp_nginx_requests": 67,
    "ghost_xhttp_unique_clients": 0,
    "privacy_ok": true
  },
  "rollback_dry_run": {
    "confirm_required": "ROLLBACK_GHOST_FALLBACKS",
    "decision": "ROLLBACK_DRY_RUN",
    "mode": "delivery-only",
    "ok": true,
    "service_stop_confirm_required": null
  },
  "rollback_drill": {
    "after_restore": {
      "env_flags": {
        "ENABLE_GHOST_HTTPS_WS_FALLBACK": "1",
        "ENABLE_GHOST_XHTTP_FALLBACK": "1",
        "EXPOSE_FALLBACK_TRANSPORTS": "1"
      },
      "ghost-access-nl-https-ws.service": "active",
      "ghost-access-nl-xhttp.service": "active",
      "status_api_health_ok": true,
      "telegram-bot-simple.service": "active",
      "x-ui": "active"
    },
    "after_rollback": {
      "env_flags": {
        "ENABLE_GHOST_HTTPS_WS_FALLBACK": "0",
        "ENABLE_GHOST_XHTTP_FALLBACK": "0",
        "EXPOSE_FALLBACK_TRANSPORTS": "0"
      },
      "ghost-access-nl-https-ws.service": "active",
      "ghost-access-nl-xhttp.service": "active",
      "status_api_health_ok": true,
      "telegram-bot-simple.service": "active",
      "x-ui": "active"
    },
    "finished_at": "2026-06-01T21:58:20Z",
    "rollback_apply": {
      "decision": "ROLLBACK_APPLIED",
      "ok": true,
      "rc": 0
    },
    "started_at": "2026-06-01T21:58:15Z"
  },
  "reality_canary_after_rollback_restore": {
    "canary": "vless_reality_local_xray",
    "results": [
      {
        "http_code": 204,
        "ok": true,
        "port": 443,
        "rc": 0,
        "total_s": 0.054668
      },
      {
        "http_code": 204,
        "ok": true,
        "port": 2083,
        "rc": 0,
        "total_s": 0.049161
      }
    ]
  }
}
```
