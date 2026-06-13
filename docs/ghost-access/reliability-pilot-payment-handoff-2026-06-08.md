# Ghost Access Reliability Pilot Payment Handoff - 2026-06-08

## Plain Status

Use this document when a buyer is ready to pay for Starter Incident Support or
the 7-day Ghost Access Reliability Pilot. This is a payment handoff, not proof
that money was received.

## Products

| Product | Price | Output |
|---|---:|---|
| Starter Incident Support | 3,000-7,000 RUB one-time | One redacted incident note using `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`. |
| Team Reliability Pilot | 15,000-40,000 RUB for 7 days | Daily health summary, incident timeline, rollback/failover checklist, final report. |

## Safe Payment Rules

- Confirm scope before payment.
- Confirm the exact amount before payment.
- Confirm the payment method before payment.
- Do not collect private keys, seed phrases, wallet recovery words, card
  numbers, raw subscription links, UUIDs, QR codes, bot tokens, or database
  dumps.
- Do not mark funds as received until the local operator verifies the receipt,
  transaction hash, or payment-provider record.
- Do not claim production readiness, guaranteed bypass, anonymity, or
  settlement finality.

## Payment Options

### Existing Wallet Intake

For wallet-based payment, use:
`docs/commercial/PAYMENT_INTAKE.md`

Important rule: do not guess the chain. The buyer and operator must agree the
exact EVM network and payment asset before payment. EVM means an
Ethereum-compatible chain; the exact chain and the exact coin/token being
transferred still have to be named explicitly before any transfer.

Use the existing payment reference from that document:
`X0T-PILOT-6017E099`

### Non-Wallet Payment

For bank, card, invoice, or local payment provider flow, record only safe
metadata in the tracker:

- provider name;
- agreed amount;
- local reference or invoice number;
- verification status;
- redacted receipt path if there is one.

Do not store card numbers, full personal documents, private payment account
screenshots, or credentials in the repository or chat.

## Buyer Message: Starter Incident

```text
Это уже платный разбор, потому что тут нужно не просто дать совет, а проверить
признаки и собрать короткий вывод.

Формат: Starter Incident Support.
Цена: 3,000-7,000 RUB.
Результат: что видно пользователю, что проверено, вероятная причина, что делать
дальше. Без передачи секретов в чат.

Перед оплатой фиксируем сумму, способ оплаты и reference. Не присылай приватные
ключи, seed phrases, raw subscription links, UUID, QR-коды, токены или
скриншоты с секретами.
```

## Buyer Message: 7-Day Pilot

```text
Это подходит под 7-дневный reliability-пилот: тут важны не только разовый ответ,
но и ежедневная сводка, timeline инцидентов и финальный отчёт.

Формат: Team Reliability Pilot.
Цена: 15,000-40,000 RUB за 7 дней.
Результат: ежедневный green/yellow/red статус, redacted incident timeline,
rollback/failover checklist и финальный отчёт.

Перед оплатой фиксируем сумму, способ оплаты и reference. Не присылай приватные
ключи, seed phrases, raw subscription links, UUID, QR-коды, токены или
скриншоты с секретами.
```

## Operator Checklist

1. Confirm the product: `starter-incident` or `7-day-pilot`.
2. Confirm the buyer-visible output.
3. Confirm the exact price and currency.
4. Confirm the payment method.
5. For wallet payment, confirm the exact network, payment asset, amount, and
   reference.
6. For non-wallet payment, confirm the invoice/reference and safe receipt path.
7. Verify payment locally.
8. Update the tracker only after verification.
9. Start delivery using the intake template.
10. For `starter-incident`, deliver
    `docs/templates/GHOST_ACCESS_STARTER_INCIDENT_NOTE_TEMPLATE.md`.

## Tracker Fields

Use these safe values in
`docs/ghost-access/reliability-pilot-tracker-2026-06-07.md`:

- `Payment ask`: `yes/no`
- `Payment method`: `wallet` / `invoice` / `local-provider` / `unknown`
- `Payment reference`: local reference only, no secrets
- `Payment verification`: `not-started` / `pending` / `verified` / `failed`
- `Delivery status`: `not-started` / `intake` / `in-progress` / `delivered`

## Claim Boundary

Allowed claim:

- payment handoff is ready;
- a buyer can be told how to pay safely.

Not allowed without separate evidence:

- funds received;
- settlement finality;
- live customer traffic;
- production readiness;
- guaranteed access reliability.
