# NL Anti-Block Client Compatibility Runtime Probe - 2026-06-02

## Decision

`NL_CLIENT_COMPAT_RUNTIME_READY`

Read-only probe. It does not copy files, restart services, reload systemd, or store raw SSH config, IP addresses, subscription URLs, VPN links, UUIDs, emails, handles, phone numbers, or client rows.

## Endpoints

| Endpoint | Result |
| --- | --- |
| /transport-usage | ok=true; xhttp=true; ws=true; privacy=true |
| /client-compatibility | http=200; ok=true; complete=false; missing=android_happ_or_hiddify, mobile_network, restricted_or_work_wifi |
| /client-compatibility contract | session_ok=true; transport=reality; port=443 |

## Wiring

| Item | Status |
| --- | --- |
| summary file | true |
| matrix file | true |
| service unit | true |
| timer unit | true |
| timer enabled | enabled |
| timer active | active |

## Required Actions

``
