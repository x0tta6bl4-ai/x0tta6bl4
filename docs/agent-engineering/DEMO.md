# Agent Work Receipt Gate Demo

This demo package shows a passing receipt and expected failure cases for the
Agent Work Receipt Gate.

## Passing Case

Use `products/agent-work-receipt-gate/receipts/valid.json` with:

```bash
python3 scripts/agents/agent_work_receipt_gate.py validate \
  --policy products/agent-work-receipt-gate/policy.example.json \
  --receipt products/agent-work-receipt-gate/receipts/valid.json \
  --json
```

The result must contain `"ok": true`.

## Failure Case

`invalid-missing-verification.json` omits the verification list and must fail
with `handoff.invalid.missing_verification`.
