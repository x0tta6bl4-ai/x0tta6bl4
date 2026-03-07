# DAO Executor Webhook Runbook

This runbook describes how to run `src/dao/executor_webhook.py` in both modes:
- `poll` mode: scans `ProposalExecuted` events on-chain.
- `webhook` mode: accepts `POST /webhook/proposal-executed` and triggers release automation.

## 1. Required Environment

```bash
export GOVERNANCE_ADDR=0xYourGovernanceContract
export TOKEN_ADDR=0xYourTokenContract
export RPC_URL=https://sepolia.base.org
```

Optional persistence (recommended):

```bash
export DAO_EXECUTOR_PROCESSED_FILE=src/dao/deployments/executed_proposals.json
export DAO_EXECUTOR_LEDGER_PATH=src/dao/deployments/audit.jsonl
```

## 2. Poll Mode (default)

```bash
python -m src.dao.executor_webhook
```

Or explicitly:

```bash
DAO_EXECUTOR_MODE=poll python -m src.dao.executor_webhook
```

## 3. Webhook Mode

```bash
export DAO_EXECUTOR_MODE=webhook
export DAO_EXECUTOR_HOST=0.0.0.0
export DAO_EXECUTOR_PORT=8090
export DAO_EXECUTOR_WEBHOOK_TOKEN=change-me
python -m src.dao.executor_webhook
```

Health and status checks:

```bash
curl -s http://127.0.0.1:8090/healthz
curl -s http://127.0.0.1:8090/status
```

Example webhook call:

```bash
curl -s -X POST http://127.0.0.1:8090/webhook/proposal-executed \
  -H "Content-Type: application/json" \
  -H "X-Executor-Token: ${DAO_EXECUTOR_WEBHOOK_TOKEN}" \
  -d '{"proposal_id":42,"title":"HELM_UPGRADE: Version 3.4.1","source":"dao-event-listener"}'
```

## 4. Idempotency and Audit

- `proposal_id` is executed once (duplicate events are skipped).
- Every processed proposal appends a JSON line to `DAO_EXECUTOR_LEDGER_PATH`.
- Processed IDs are persisted to `DAO_EXECUTOR_PROCESSED_FILE`.

## 5. Upgrade Trigger Rules

`trigger_upgrade()` is called only when proposal title contains:
- `HELM_UPGRADE`
- `DEPLOY`

The executor runs:

```bash
bash scripts/release_to_main.sh
```

with environment:
- `DAO_PROPOSAL_ID`
- `DAO_PROPOSAL_TITLE`
