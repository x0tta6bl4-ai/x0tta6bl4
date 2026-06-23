# NL Anti-Block Client Evidence Plan - 2026-06-02

## Decision

`CLIENT_EVIDENCE_REQUIRED`

This file contains only safe evidence instructions. Do not store VPN links, UUIDs, raw IPs, emails, usernames, subscription tokens, QR codes, or screenshots that reveal secrets.

## Current Status

`missing_requirements=android_happ_or_hiddify, mobile_network, restricted_or_work_wifi`

| Requirement | Proven |
| --- | --- |
| desktop_v2rayn | true |
| android_happ_or_hiddify | false |
| mobile_network | false |
| restricted_or_work_wifi | false |

## ADB Context

| ADB Available | Connected Devices | State Counts | Raw Serials Stored |
| --- | --- | --- | --- |
| true | 0 |  | false |

## Latest Android ADB Probe

| Decision | OK | VPN Seen | Dataplane OK | HTTP Code | Tool |
| --- | --- | --- | --- | --- | --- |
| ANDROID_DEVICE_NOT_CONNECTED | false | false | false | 0 | not_run |

## Required Tasks

| Requirement | Client | Network | Transport | Port |
| --- | --- | --- | --- | --- |
| android_happ_or_hiddify | Happ | mobile | reality | 443 |
| restricted_or_work_wifi | any | work-wifi | reality | 443 |
| mobile_network | Happ | mobile | reality | 443 |

## Safe Recorder Commands

Task 1: `android_happ_or_hiddify`

```bash
python3 services/nl-server/ghost-access/record_client_compatibility.py --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md --add-check --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --json
```

Remote client evidence command:

```bash
python3 services/nl-server/ghost-access/record_remote_client_evidence.py --write --record-matrix --evidence-source remote_user_report --reporter-label remote-city-user --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --json
```

Android ADB auto-record command:

```bash
python3 services/nl-server/ghost-access/probe_android_adb_vpn.py --write --json --record-matrix --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443
```

Task 2: `restricted_or_work_wifi`

```bash
python3 services/nl-server/ghost-access/record_client_compatibility.py --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md --add-check --client "any" --client-version unknown --network-type work-wifi --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --json
```

Remote client evidence command:

```bash
python3 services/nl-server/ghost-access/record_remote_client_evidence.py --write --record-matrix --evidence-source remote_user_report --reporter-label remote-city-user --client "any" --client-version unknown --network-type work-wifi --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --json
```

Android ADB auto-record command:

```bash
python3 services/nl-server/ghost-access/probe_android_adb_vpn.py --write --json --record-matrix --client "any" --client-version unknown --network-type work-wifi --transport reality --port 443
```

Task 3: `mobile_network`

```bash
python3 services/nl-server/ghost-access/record_client_compatibility.py --matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json --markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md --add-check --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --json
```

Remote client evidence command:

```bash
python3 services/nl-server/ghost-access/record_remote_client_evidence.py --write --record-matrix --evidence-source remote_user_report --reporter-label remote-city-user --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443 --result <pass|fail> --symptom "<short result, no secrets>" --json
```

Android ADB auto-record command:

```bash
python3 services/nl-server/ghost-access/probe_android_adb_vpn.py --write --json --record-matrix --client "Happ" --client-version unknown --network-type mobile --transport reality --port 443
```
