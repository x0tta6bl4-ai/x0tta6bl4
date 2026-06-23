# Ghost Access Reliability Pilot Day 1 Runbook - 2026-06-08

## Plain Status

Day 1 is for outreach and signal, not engineering. The expected visible result
is 10 direct messages sent, every reply tracked, and at least one serious reply
moved into safe intake.

## Inputs

- Outreach sheet: `docs/ghost-access/reliability-pilot-outreach-2026-06-07.md`
- Tracker: `docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`
- Payment handoff: `docs/ghost-access/reliability-pilot-payment-handoff-2026-06-08.md`
- Intake template: `docs/templates/GHOST_ACCESS_RELIABILITY_INTAKE_TEMPLATE.md`
- Starter incident note template:
  `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`
- Daily summary template: `docs/templates/GHOST_ACCESS_DAILY_HEALTH_SUMMARY_TEMPLATE.md`

## Before Sending

1. Pick 10 contacts from these segments:
   - remote worker;
   - small team;
   - builder or VPS user;
   - existing access user.
2. Give each contact a local nickname in the tracker.
3. Do not store private handles, phone numbers, raw profile links, UUIDs, or
   subscription links in the tracker.
4. Use the direct message from the outreach sheet.

## Send

Send 10 direct messages.

Expected result: tracker rows 1-10 have `Message sent` set to `yes` and a date.

## If Someone Replies

1. Do not ask for a subscription link, UUID, QR code, token, private key, or
   screenshot with credentials.
2. Send the follow-up from the outreach sheet.
3. Fill one `Intake Log` entry in the tracker.
4. If the pain is real and urgent, classify fit:
   - `starter-incident`;
   - `7-day-pilot`;
   - `not-fit`.

## When To Ask For Payment

Ask for payment when all are true:

- there is a real current symptom;
- the user wants a result, not only free advice;
- the next step requires your time to diagnose, monitor, or write a report;
- the scope fits the starter incident or 7-day pilot.

Use this wording:

```text
Это уже похоже на платный разбор, потому что тут нужно не просто советом
ответить, а проверить признаки и собрать короткий вывод.

Могу взять как starter incident: 3-7 тыс. RUB. Результат: что сломано, что
проверено, что делать дальше, без передачи секретов в чат.
```

If the user agrees, switch to
`docs/ghost-access/reliability-pilot-payment-handoff-2026-06-08.md` before
sharing payment details. Expected result: product, amount, payment method, and
reference are fixed before payment.

For a paid starter incident, deliver
`docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`.

## End Of Day 1

Update tracker:

- Direct messages sent:
- Replies:
- Serious replies:
- Best user wording:
- Blocker:
- Tomorrow action:

## Day 1 Success

Day 1 is successful if one is true:

- 10 direct messages sent;
- 2+ replies;
- 1 safe intake started;
- 1 clear refusal reason recorded.

Day 1 is not successful if no messages were sent.

## Engineering Rule

Do not write code on Day 1 unless a real reply requires a safer diagnostic,
redacted report, or daily health summary to close a paid ask.
