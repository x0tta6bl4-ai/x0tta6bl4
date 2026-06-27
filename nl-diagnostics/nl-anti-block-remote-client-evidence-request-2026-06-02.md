# NL Anti-Block Remote Client Evidence Request - 2026-06-02

## Decision

`REMOTE_CLIENT_EVIDENCE_REQUEST_READY`

This packet contains safe request text and operator commands for collecting the remaining real-client evidence. It must not contain VPN links, subscription URLs, QR codes, UUIDs, raw IPs, emails, handles, phone numbers, screenshots, logs, or personal identifiers.

## Summary

| Missing Requirements | Minimum Reports Required | Request Count |
| --- | --- | --- |
| android_happ_or_hiddify, mobile_network, restricted_or_work_wifi | 2 | 2 |

Freshness policy:

```text
record_remote_client_evidence_reply.py rejects request packets older than 24 hours; refresh this packet before recording delayed replies
```

Request packet hash binding policy:

```text
record_remote_client_evidence_reply.py supports --expect-request-packet-sha256; before recording a reply, bind it to the exact request artifact hash from scripts/vpn_status.sh --json client_evidence.remote_request_packet.source_sha256 or from sha256sum of this request packet
```

## Requests

### remote-client-evidence-1

| Covers | Client | Network | Transport | Port | Evidence Session | Session Started At |
| --- | --- | --- | --- | --- | --- | --- |
| android_happ_or_hiddify, mobile_network | Happ | mobile | reality | 443 | nl-anti-block-2026-06-02 | 2026-06-02T00:00:00Z |

Tester message:

```text
Test remote-client-evidence-1: use Happ or Hiddify on mobile data, not Wi-Fi. Select the active Ghost Access Reality profile on port 443. Open any normal encrypted website or app through the VPN. Reply only with: pass connected, fail timeout, fail import, or fail no-internet. Do not send profile links, subscription links, QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, screenshots, or logs.
```

Direct record command policy:

```text
Direct record_remote_client_evidence.py --write commands are disabled in this remote request packet; record tester replies only through operator_reply_record_* commands so every persisted reply is bound to the current request packet SHA-256.
```

Record pass from short reply:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --write --record-matrix --refresh-artifacts --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-1 --reply-stdin --json
```

Validate pass reply without writing:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-1 --reply-stdin --json
```

Record fail from short reply:

```bash
printf '%s\n' "fail timeout" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --write --record-matrix --refresh-artifacts --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-1 --reply-stdin --json
```

Validate fail reply without writing:

```bash
printf '%s\n' "fail timeout" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-1 --reply-stdin --json
```

Allowed short replies:

```text
pass connected, fail timeout, fail import, fail no-internet
```

### remote-client-evidence-2

| Covers | Client | Network | Transport | Port | Evidence Session | Session Started At |
| --- | --- | --- | --- | --- | --- | --- |
| restricted_or_work_wifi | any | work-wifi | reality | 443 | nl-anti-block-2026-06-02 | 2026-06-02T00:00:00Z |

Tester message:

```text
Test remote-client-evidence-2: use Happ or Hiddify on the restricted or work Wi-Fi. Select the active Ghost Access Reality profile on port 443. Open any normal encrypted website or app through the VPN. Reply only with: pass connected, fail timeout, fail import, or fail no-internet. Do not send profile links, subscription links, QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, screenshots, or logs.
```

Direct record command policy:

```text
Direct record_remote_client_evidence.py --write commands are disabled in this remote request packet; record tester replies only through operator_reply_record_* commands so every persisted reply is bound to the current request packet SHA-256.
```

Record pass from short reply:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --write --record-matrix --refresh-artifacts --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-2 --reply-stdin --json
```

Validate pass reply without writing:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-2 --reply-stdin --json
```

Record fail from short reply:

```bash
printf '%s\n' "fail timeout" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --write --record-matrix --refresh-artifacts --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-2 --reply-stdin --json
```

Validate fail reply without writing:

```bash
printf '%s\n' "fail timeout" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-2 --reply-stdin --json
```

Allowed short replies:

```text
pass connected, fail timeout, fail import, fail no-internet
```
