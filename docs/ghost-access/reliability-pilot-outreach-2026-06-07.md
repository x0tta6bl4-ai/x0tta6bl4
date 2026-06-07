# Ghost Access Reliability Pilot Outreach Sheet - 2026-06-07

## Status

Use this sheet to start the first 20 direct conversations. The target is not a
large launch. The target is one paid pilot, one deposit, or clear refusal
reasons.

## Rules

- Do not send raw subscription links in chat.
- Do not ask for private keys, UUIDs, tokens, QR codes, or database dumps.
- Do not promise unblockable access, anonymity, guaranteed DPI bypass, or
  production SLOs.
- Do not change live subscriptions during outreach.
- Move technical work to the intake template only after the user agrees.

## Direct Message

```text
Привет. Я открываю 1-2 коротких reliability-пилота для людей или маленьких
команд, у которых нестабильный VPN/proxy/remote access.

Формат безопасный: без приватных ключей, raw subscription links, UUID, токенов
и скриншотов с секретами. Сначала фиксируем симптом, потом я даю понятный
вывод: что сломано, что проверено, что делать дальше.

Есть два формата:
1. Разовый разбор инцидента: 3-7 тыс. RUB.
2. 7-дневный reliability-пилот: 15-40 тыс. RUB.

Если сейчас есть живая проблема, могу взять один случай.
```

## Follow-Up If Interested

```text
Ок. Тогда начнём безопасно: не присылай ссылку подписки, UUID, QR-код или токен.

Ответь только на это:
1. Что видно пользователю: timeout, не грузит сайт, не подключается клиент?
2. На каком устройстве и клиенте?
3. Когда началось?
4. Сколько людей задеты?
5. Что будет считаться хорошим результатом?

После этого я скажу, подходит ли это под разовый разбор или 7-дневный пилот.
```

## Follow-Up If Price Objection

```text
Понял. Чтобы не спорить о цене: что сделало бы это платным для тебя?

Варианты: быстрее понять причину, ежедневная сводка, отчёт для команды,
failover checklist, помощь с конкретным клиентом/устройством, другое.
```

## Tracking Table

Use the working tracker for real outreach:
`docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`

| Date | Contact | Segment | Message sent | Reply | Call/intake | Paid ask | Outcome | Refusal reason |
|---|---|---|---|---|---|---|---|---|
| `YYYY-MM-DD` | | | `yes/no` | | | | | |

## Daily Minimum

- Send 10 direct messages.
- Record every reply or non-reply.
- Ask for payment by day 3 if the problem is real.
- Rewrite the offer from real refusal words by day 7.

## Links

- Pilot packet: `docs/ghost-access/reliability-pilot-packet-2026-06-07.md`
- Pilot tracker: `docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`
- Intake template: `docs/templates/GHOST_ACCESS_RELIABILITY_INTAKE_TEMPLATE.md`
- Report template: `docs/templates/GHOST_ACCESS_RELIABILITY_REPORT_TEMPLATE.md`
