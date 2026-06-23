# NL Anti-Block Remote Client Evidence Intake - 2026-06-02

## Decision

`REMOTE_CLIENT_EVIDENCE_INTAKE_READY`

This file stores only privacy-safe remote client evidence metadata. Do not store VPN links, subscription URLs, UUIDs, raw IPs, emails, Telegram handles, phone numbers, QR codes, or screenshots.

## Matrix Summary

| Complete | Missing Requirements | Real Checks | Passing Checks |
| --- | --- | --- | --- |
| false | android_happ_or_hiddify, mobile_network, restricted_or_work_wifi | 9 | 2 |

| Requirement | Proven |
| --- | --- |
| desktop_v2rayn | true |
| android_happ_or_hiddify | false |
| mobile_network | false |
| restricted_or_work_wifi | false |

## Latest Candidate

| Source | Reporter Label | Client | Network | Transport | Port | Status | Symptom |
| --- | --- | --- | --- | --- | --- | --- | --- |
| none |  |  |  |  |  |  |  |

## Safe Remote Record Command

```bash
python3 services/nl-server/ghost-access/record_remote_client_evidence.py --write --record-matrix --evidence-source remote_user_report --reporter-label remote-city-user --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --evidence-session-id nl-anti-block-2026-06-02 --json
```
