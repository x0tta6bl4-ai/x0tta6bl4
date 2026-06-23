# NL Anti-Block Client Compatibility Runtime Summary - 2026-06-02

## Decision

`CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED`

This is the safe summary intended for the local status API `/client-compatibility`. It does not include raw client rows, symptoms, VPN links, UUIDs, raw IPs, emails, Telegram handles, phone numbers, QR codes, or screenshots.

## Completion

| Requirement | Proven |
| --- | --- |
| desktop_v2rayN | true |
| android_happ_or_hiddify | false |
| mobile_network | false |
| restricted_or_work_wifi | false |

## Counts

| Complete | Missing | Real Checks | Passing Checks |
| --- | --- | --- | --- |
| false | android_happ_or_hiddify, mobile_network, restricted_or_work_wifi | 9 | 2 |

## Evidence Session

| ID | Started At | Required Transport | Required Port | Current Session Passes |
| --- | --- | --- | --- | --- |
| nl-anti-block-2026-06-02 | 2026-06-02T00:00:00Z | reality | 443 | 0 |
