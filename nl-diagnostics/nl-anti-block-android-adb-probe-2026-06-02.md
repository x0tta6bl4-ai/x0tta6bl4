# NL Anti-Block Android ADB VPN Probe - 2026-06-02

## Decision

`ANDROID_DEVICE_NOT_CONNECTED`

This probe stores only aggregate ADB/device/runtime/dataplane status. It does not store ADB serials, VPN links, UUIDs, raw IPs, emails, subscription tokens, QR codes, screenshots, or connectivity dumps.

## ADB

| ADB Available | Connected Devices | State Counts | Raw Serials Stored |
| --- | --- | --- | --- |
| true | 0 |  | false |

## Runtime

| VPN Transport Seen | Connectivity Dump Stored |
| --- | --- |
| false | false |

## Dataplane

| OK | HTTP Code | Tool | Target URL Class | Raw Response Stored |
| --- | --- | --- | --- | --- |
| false | 0 | not_run | https_generate_204 | false |

## Matrix Recording

| Attempted | Recorded | Reason | Result | Matrix Path |
| --- | --- | --- | --- | --- |
| false | false | record_matrix_not_requested |  |  |
