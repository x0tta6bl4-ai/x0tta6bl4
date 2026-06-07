# NL Anti-Block Client Compatibility Matrix - 2026-06-02

## Decision

`CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED`

This file is generated from the JSON matrix. Keep JSON as the source of truth and use the recorder CLI to add real checks.

No VPN links, UUIDs, raw IPs, emails, subscription tokens, or client hashes are stored here.

## Completion

`complete=false`; `passing_real_client_checks=2`; `real_client_checks=9`.

`missing_requirements=android_happ_or_hiddify, mobile_network, restricted_or_work_wifi`.

`evidence_session_id=nl-anti-block-2026-06-02`. Mobile/work-Wi-Fi pass evidence must use this session id.

| Requirement | Proven |
| --- | --- |
| Desktop v2rayN | true |
| Android Happ/Hiddify | false |
| Mobile network | false |
| Restricted/work Wi-Fi | false |

## Next Required Checks

| Requirement | Client | Network | Transport | Port |
| --- | --- | --- | --- | --- |
| Android Happ/Hiddify | Happ | mobile | reality | 443 |
| Restricted/work Wi-Fi | any | work-wifi | reality | 443 |

## Proven Server-Side

| Case | Transport | Port | Evidence | Status |
| --- | --- | --- | --- | --- |
| subscription_contains_legacy_and_fallback_profiles | reality, xhttp, ws |  | line_count=20; counts=xhttp=5, ws=5, reality=10, other=0; ports=443, 2083, 8443 | pass |
| legacy_reality_canary_after_rollback_restore | reality | 443 | http_code=204; total_s=0.054668 | pass |
| secondary_reality_canary_after_rollback_restore | reality | 2083 | http_code=204; total_s=0.049161 | pass |
| xhttp_fallback_readiness | xhttp | 8443 | ghost_xhttp_ready=true; nginx_counter_present=true | pass |
| websocket_fallback_readiness | ws | 8443 | ghost_https_ws_ready=true; nginx_counter_present=true | pass |
| delivery_only_rollback_drill |  |  | decision=ROLLBACK_APPLIED; critical_services_stayed_active=true | pass |

## Required Real Client Checks

| Client | Version | Network | Transport | Port | Status | Evidence Session | Checked At | Symptom |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2rayN | unknown | desktop | xhttp | 8443 | pass |  | 2026-06-01T23:03:50Z | bundled Xray profile probe HTTP 204 |
| v2rayN | unknown | desktop | ws | 8443 | pass |  | 2026-06-01T23:03:50Z | bundled Xray profile probe HTTP 204 |
| v2rayN | unknown | windows | reality | 443 | not_tested |  |  |  |
| Happ/Hiddify | unknown | mobile | xhttp | 8443 | not_tested |  |  |  |
| Happ/Hiddify | unknown | mobile | ws | 8443 | not_tested |  |  |  |
| Happ/Hiddify | unknown | mobile | reality | 443 | not_tested |  |  |  |
| any | unknown | work-wifi | xhttp | 8443 | not_tested |  |  |  |
| any | unknown | work-wifi | ws | 8443 | not_tested |  |  |  |
| remote-user-city-case | unknown | unknown | preferred-working-fallback |  | not_tested |  |  |  |

## Local Client Inventory

| Source | Diagnosis | Reality | XHTTP | WS | Ports |
| --- | --- | --- | --- | --- | --- |
| local_v2rayn_gui_db | local_v2rayn_db_contains_fallback_profiles | 6 | 1 | 1 | 443, 2083, 8443, 39829 |
| enabled_subscription_fetch | subscription_aggregate | 2 | 1 | 1 | 443, 2083, 8443 |

## Local Import Copy-Test

| Decision | Live DB Mutated | Inserted XHTTP | Inserted WS | Remaining Missing | Copy Counts After Import |
| --- | --- | --- | --- | --- | --- |
| APPLIED_TO_COPY | false | 1 | 1 | 0 | reality=6, xhttp=1, ws=1, other=0 |

## Local Live Import

| Decision | Live DB Mutated | Restarted v2rayN | Inserted XHTTP | Inserted WS | Remaining Missing | Backup |
| --- | --- | --- | --- | --- | --- | --- |
| APPLIED_TO_LIVE_DB | true | false | 1 | 1 | 0 | recorded |

## Local Dataplane Probe

| Source | OK | Passed Transports | Profile Count |
| --- | --- | --- | --- |
| local_v2rayn_db_profiles_with_v2rayn_bundled_xray | true | ws, xhttp | 2 |

| Transport | Port | HTTP Code | Total Seconds | OK |
| --- | --- | --- | --- | --- |
| ws | 8443 | 204 | 0.555399 | true |
| xhttp | 8443 | 204 | 0.490398 | true |

## Safe Recorder

Add real client evidence with the local privacy-safe recorder:

```bash
python3 services/nl-server/ghost-access/record_client_compatibility.py \
  --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json \
  --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md \
  --add-check \
  --checked-at 2026-06-02T01:00:00Z \
  --client v2rayN \
  --client-version unknown \
  --network-type desktop \
  --transport reality \
  --port 443 \
  --result pass \
  --symptom "connected normal HTTPS sites" \
  --evidence-session-id nl-anti-block-2026-06-02 \
  --json
```

Validate and regenerate Markdown without adding a result:

```bash
python3 services/nl-server/ghost-access/record_client_compatibility.py \
  --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json \
  --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md \
  --validate \
  --json
```

Do not store subscription URLs, `/sub/...` tokens, VLESS links, UUIDs, raw IP addresses, emails, Telegram IDs, usernames, QR codes, or screenshots that show secrets.
