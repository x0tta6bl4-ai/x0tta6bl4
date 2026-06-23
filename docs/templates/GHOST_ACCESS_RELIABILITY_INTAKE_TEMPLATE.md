# Ghost Access Reliability Intake Template

## Status

Use this template before running diagnostics. It collects symptoms without
asking the user to paste secrets into chat.

## Private Data Rule

Do not send:

- private keys;
- raw subscription URLs;
- UUIDs;
- bot tokens;
- Telegram bot admin tokens;
- database dumps;
- wallet keys;
- screenshots that show credentials, profile links, QR codes, or full URLs.

If a local command needs a secret, run it locally and paste only the redacted
result.

## Contact And Scope

- Contact name or handle:
- Organization or team:
- Timezone:
- Pilot type: `starter-incident` / `7-day-reliability-pilot`
- Access path nickname, without secrets:
- Is this path currently used by real users: `yes` / `no` / `unknown`

## Symptom

- What is visibly broken:
- When it started:
- How often it happens:
- Affected app/site/protocol:
- Device and OS:
- Client app:
- Network type: `mobile` / `wifi` / `office` / `server` / `other`
- Region or city, if safe to share:
- Does direct access work without VPN/proxy:
- Does access work through a different network:

## Impact

- Number of affected users:
- Business impact:
- Is this blocking work right now:
- Desired visible result:

## Safe Evidence

Only include redacted values.

- Error text, with secrets removed:
- HTTP status code, if known:
- Client status: `connected` / `connecting` / `timeout` / `auth failed` / `unknown`
- Last known good time:
- Last known bad time:
- Any recent change, without secrets:

## Allowed Checks

Mark what the user allows.

- [ ] Read-only server health check.
- [ ] Read-only subscription status check.
- [ ] Read-only client compatibility check.
- [ ] Redacted incident timeline.
- [ ] Daily health summary.
- [ ] No production mutation without separate approval.

## First Decision

- Current status: `green` / `yellow` / `red` / `unknown`
- First hypothesis:
- First safe next check:
- Payment status: `not asked` / `asked` / `paid` / `refused`
- Refusal reason, if any:
