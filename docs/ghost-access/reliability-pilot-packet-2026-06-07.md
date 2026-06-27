# Ghost Access Reliability Pilot Packet - 2026-06-07

## Plain Status

This packet turns the revenue sprint into one sellable pilot. It is not a
production-readiness claim and it does not require changing existing Ghost
Access subscriptions.

## Offer

**Name:** Ghost Access Reliability Pilot

**Duration:** 7 days

**Price band:** 15,000-40,000 RUB for one access path.

**Buyer fit:**

- a small team or operator that depends on stable remote access;
- a user group with recurring VPN/proxy incidents;
- a builder who wants someone to diagnose access failures without receiving
  private keys, raw subscription URLs, bot tokens, UUIDs, or database dumps.

## Promise

For one agreed access path, deliver:

- safe symptom intake;
- daily red/yellow/green health summary;
- redacted incident timeline;
- one rollback or failover checklist;
- final reliability report with renewal recommendation.

## Non-Promises

Do not claim:

**Goal:** unblockable access — this is an aspirational target, not currently achieved.
- anonymity;
- guaranteed DPI bypass;
- production SLO proof;
- external provider correctness;
- customer traffic delivery beyond the observed pilot path.

## Scope

### Included

- Review symptoms using the intake template.
- Check existing redacted evidence and diagnostics.
- Run only safe local or server-side diagnostics that do not expose secrets.
- Explain likely causes in plain language.
- Recommend one next action at a time.
- Keep a daily status line and final report.

### Excluded

- Raw subscription link collection in chat.
- Private keys, UUIDs, bot tokens, wallet keys, or database dumps.
- Destructive production service changes.
- NL `x-ui.service` or `xray` stop/disable/mask operations.
- Broad MaaS architecture audit.
- Full PQC/eBPF production certification.

## Intake Flow

Use [GHOST_ACCESS_RELIABILITY_INTAKE_TEMPLATE.md](../templates/GHOST_ACCESS_RELIABILITY_INTAKE_TEMPLATE.md).

Expected result: the user can describe the symptom without sending secrets.

## Daily Operating Loop

1. Record status as green, yellow, or red.
2. Record one visible user symptom or "no user-visible issue".
3. Record evidence used, with only redacted paths or hashes.
4. Record action taken or "observe only".
5. Record next check time.

Daily summary template:
`docs/templates/GHOST_ACCESS_DAILY_HEALTH_SUMMARY_TEMPLATE.md`

## Evidence To Use

Allowed examples:

- `STATUS_REALITY.md` for project truth baseline.
- `plans/REVENUE_USEFULNESS_SPRINT_2026-05-31.md` for commercial sprint scope.
- `docs/ghost-access/spb-beta-rollout.md` for rollout constraints and no-change rules.
- `docs/runbooks/NL_VPN_HEALTH.md` for read-only diagnostic conventions.
- `nl-diagnostics/*.md` reports that already redact sensitive identifiers.
- `services/nl-server/ghost-access/` tools only when they are read-only or explicitly safe.

## Pilot Success Criteria

The pilot is useful if at least one is true:

- one paid pilot or deposit is received;
- one incident is resolved or explained well enough that the user can act;
- three refusal reasons are recorded and the offer is rewritten from real user words.

The pilot is not useful if:

- nobody agrees to a call or async triage after direct outreach;
- users only want free repair with no paid follow-up;
- the visible pain is unrelated to access reliability.

## First Outreach Text

Operational outreach sheet:
`docs/ghost-access/reliability-pilot-outreach-2026-06-07.md`

Day 1 runbook:
`docs/ghost-access/reliability-pilot-day1-runbook-2026-06-08.md`

Day 2-3 conversion runbook:
`docs/ghost-access/reliability-pilot-day2-day3-conversion-runbook-2026-06-08.md`

Working tracker:
`docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`

Payment handoff:
`docs/ghost-access/reliability-pilot-payment-handoff-2026-06-08.md`

```text
Привет. Я открываю 1-2 коротких reliability-пилота для команд или людей,
у которых нестабильный VPN/proxy/remote access.

Формат безопасный: без передачи приватных ключей, raw subscription links, UUID,
токенов или скриншотов с секретами. Сначала фиксируем симптом, потом я даю
понятный статус: что сломано, что проверено, что делать дальше.

Пилот на 7 дней: ежедневная красная/жёлтая/зелёная сводка, timeline инцидентов,
короткий rollback/failover checklist и финальный отчёт. Цена зависит от объёма:
15-40 тыс. RUB.
```

## One-Time Starter Alternative

If 7 days is too large, offer a starter incident support slot:

- price: 3,000-7,000 RUB one-time;
- output: one redacted incident note;
- rule: if the likely cause cannot be explained, do not charge.

When the buyer is ready to pay, use
`docs/ghost-access/reliability-pilot-payment-handoff-2026-06-08.md`.

For delivery, use
`docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`.

## Final Report

Use [GHOST_ACCESS_RELIABILITY_REPORT_TEMPLATE.md](../templates/GHOST_ACCESS_RELIABILITY_REPORT_TEMPLATE.md).

Expected result: the buyer gets a short report that says what improved, what did
not improve, what remains risky, and whether renewal makes sense.

## Engineering Rule

During this pilot, code work is allowed only when it directly supports the pilot:

- safer diagnostic command;
- redacted report generator;
- daily health summary;
- incident timeline;
- failover checklist.

Everything else goes to backlog.
