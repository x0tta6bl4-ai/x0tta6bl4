# Agent Work Receipt Gate

Agent Work Receipt Gate validates an AI-agent handoff receipt against the
repo's integrity ledger schema and a product-specific policy.

## Local Use

```bash
python3 scripts/agents/agent_work_receipt_gate.py validate \
  --policy products/agent-work-receipt-gate/policy.example.json \
  --receipt products/agent-work-receipt-gate/receipts/valid.json \
  --json
```

## Release Check

```bash
python3 scripts/agents/verify_agent_work_receipt_gate_release.py --json
```

The release decision is repo-local package readiness only. It does not prove
production status for Ghost Access, SPB, NL, Open5GS, or any external runtime.
