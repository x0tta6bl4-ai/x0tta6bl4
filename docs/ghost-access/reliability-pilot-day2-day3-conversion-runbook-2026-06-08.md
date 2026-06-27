# Ghost Access Reliability Pilot Day 2-3 Conversion Runbook - 2026-06-08

## Plain Status

Day 2-3 is for turning replies into either paid work or useful refusal data. Do
not keep debugging for free after the problem is clear enough to require focused
time.

Expected visible result by the end of Day 3:

- 3 safe intakes started, or a clear reason why not;
- 1 paid ask made;
- every refusal recorded in the tracker;
- one Starter Incident Note drafted if payment is verified.

## Inputs

- Outreach sheet: `docs/ghost-access/reliability-pilot-outreach-2026-06-07.md`
- Tracker: `docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`
- Intake template: `docs/templates/GHOST_ACCESS_RELIABILITY_INTAKE_TEMPLATE.md`
- Payment handoff: `docs/ghost-access/reliability-pilot-payment-handoff-2026-06-08.md`
- Starter incident note template: `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`
- Daily health summary template: `docs/templates/GHOST_ACCESS_DAILY_HEALTH_SUMMARY_TEMPLATE.md`

## Reply Classification

Classify every reply into one bucket:

| Bucket | Meaning | Next action |
|---|---|---|
| `urgent-paid-fit` | Real current access pain and user wants outcome. | Move to paid ask. |
| `triage-first` | Problem may fit, but facts are missing. | Send safe intake questions. |
| `team-pilot-fit` | Multiple users or repeated incidents. | Offer 7-day pilot. |
| `free-help-only` | User wants advice but avoids paid scope. | Log refusal, stop deep work. |
| `not-fit` | Pain is unrelated to access reliability. | Log reason, do not sell. |

## Free Triage Limit

Free triage may include:

- clarifying the visible symptom;
- checking whether the problem is current;
- identifying affected device/client/user count;
- deciding whether the case fits the offer.

Free triage must stop before:

- deep log review;
- multi-step server diagnostics;
- repair attempt;
- monitoring;
- report writing;
- rollback/failover planning.

## Paid Ask Gate

Ask for payment when all are true:

- symptom is current or recurring;
- buyer wants an outcome, not only a chat answer;
- next step needs focused diagnostic or written output;
- scope fits `starter-incident` or `7-day-pilot`;
- no secrets are needed in chat.

## Paid Ask: Starter Incident

```text
Статус: это уже платный разбор.

Почему: чтобы ответить нормально, нужно проверить признаки и собрать короткий
вывод, а не просто дать совет в чате.

Формат: Starter Incident Support.
Цена: 3,000-7,000 RUB.
Результат: короткая incident note: что видно пользователю, что проверено,
вероятная причина, что делать дальше.

Если ок, фиксируем сумму, способ оплаты и reference. Секреты не присылай:
raw subscription links, UUID, QR-коды, приватные ключи и токены не нужны.
```

## Paid Ask: 7-Day Pilot

```text
Статус: это больше похоже на 7-дневный reliability-пилот.

Почему: проблема затрагивает несколько людей или повторяется, поэтому нужен не
один совет, а наблюдение, timeline и финальный отчёт.

Формат: Team Reliability Pilot.
Цена: 15,000-40,000 RUB за 7 дней.
Результат: ежедневный green/yellow/red статус, incident timeline,
rollback/failover checklist и финальный отчёт.

Если ок, фиксируем сумму, способ оплаты и reference. Секреты не присылай:
raw subscription links, UUID, QR-коды, приватные ключи и токены не нужны.
```

## If Buyer Says Yes

1. Switch to
   `docs/ghost-access/reliability-pilot-payment-handoff-2026-06-08.md`.
2. Fix product, price, payment method, and reference.
3. Verify payment locally.
4. Update the Payment Log in
   `docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`.
5. Start delivery from the intake template.
6. For `starter-incident`, deliver
   `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`.

## If Buyer Refuses

Do not argue. Ask one question:

```text
Понял. Что должно быть по-другому, чтобы это стало платным?

Например: ниже цена, быстрее результат, гарантия формата, отчёт для команды,
разбор конкретного клиента, ежедневная сводка, другое.
```

Then record:

- refusal reason taxonomy value;
- user's exact non-secret wording;
- whether the offer needs rewrite.

## If Buyer Sends Secrets

Stop and reply:

```text
Стоп, это лучше не хранить в чате. Удали/отзови сообщение, если можешь.
Мне нужен только безопасный симптом: что видно пользователю, клиент/устройство,
когда началось и что будет хорошим результатом.
```

Do not copy the secret into the tracker, report, commit message, issue, or
diagnostic artifact.

## End Of Day 3

Update the tracker:

- Paid ask made: `yes/no`
- Paid result: `paid/refused/pending`
- Best refusal wording:
- Best buyer pain wording:
- Offer rewrite needed: `yes/no`
- Next action:

Day 3 is successful if one is true:

- one paid starter incident;
- one paid 7-day pilot or deposit;
- three clear refusal reasons that make the next offer sharper.
