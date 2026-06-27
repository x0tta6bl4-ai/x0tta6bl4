# NL Anti-Block Remote Client Reply Readiness

generated_at: `2026-06-06T17:13:33Z`
decision: `REMOTE_CLIENT_REPLIES_READY_FOR_SAFE_INTAKE`
ready_for_safe_intake: `true`
server_write_allowed: `false`
reply_recording_performed: `false`

## Gates

| ID | Status | OK | Next Step |
|---|---:|---:|---|
| `REQUEST-FRESHNESS-01` | `pass` | `true` | refresh nl-anti-block-remote-client-evidence-request before recording delayed replies |
| `REQUEST-CONTRACT-01` | `pass` | `true` | regenerate the remote client evidence request from the current matrix |
| `REQUEST-COMMANDS-01` | `pass` | `true` | regenerate request commands with reply recorder, packet hash guard, and non-writing validate commands |
| `REPLY-RECORDER-01` | `pass` | `true` | fix record_remote_client_evidence_reply.py guards before accepting tester replies |
| `GOAL-ANTIBLOCK-01` | `pass` | `true` | rebuild vpn goal status after refreshing remote request artifacts |
| `EXTERNAL-REPLIES-01` | `blocked_external_reply` | `true` | send request messages to testers and record only their short reply through --reply-stdin |

## Requests

### remote-client-evidence-1

Tester message:

```text
Test remote-client-evidence-1: use Happ or Hiddify on mobile data, not Wi-Fi. Select the active Ghost Access Reality profile on port 443. Open any normal encrypted website or app through the VPN. Reply only with: pass connected, fail timeout, fail import, or fail no-internet. Do not send profile links, subscription links, QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, screenshots, or logs.
```

Validate pass without writing:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-1 --reply-stdin --json
```

Record pass after a safe reply:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --write --record-matrix --refresh-artifacts --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-1 --reply-stdin --json
```

### remote-client-evidence-2

Tester message:

```text
Test remote-client-evidence-2: use Happ or Hiddify on the restricted or work Wi-Fi. Select the active Ghost Access Reality profile on port 443. Open any normal encrypted website or app through the VPN. Reply only with: pass connected, fail timeout, fail import, or fail no-internet. Do not send profile links, subscription links, QR codes, UUIDs, IP addresses, usernames, phone numbers, handles, screenshots, or logs.
```

Validate pass without writing:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-2 --reply-stdin --json
```

Record pass after a safe reply:

```bash
printf '%s\n' "pass connected" | python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py --write --record-matrix --refresh-artifacts --expect-request-packet-sha256 "$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json | awk '{print $1}')" --request-id remote-client-evidence-2 --reply-stdin --json
```

No NL or SPB writes were performed by this readiness report.
