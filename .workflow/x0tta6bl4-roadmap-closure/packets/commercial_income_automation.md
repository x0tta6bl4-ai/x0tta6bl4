# Packet: commercial_income_automation

## Objective

Verify and harden the commercial paid-task and non-bounty income automation
roadmap without making external submissions, charging buyers, or claiming
received funds.

## Files

- `src/sales/`
- `scripts/ops/build_non_bounty_income_map.py`
- `scripts/ops/build_paid_task_automation_plan.py`
- `scripts/ops/check_commercial_mesh_platform_readiness.py`
- `scripts/ops/run_income_watch_cycle.py`
- `scripts/ops/run_paid_task_hunter.py`
- `scripts/ops/run_paid_task_watch_loop.py`
- `scripts/ops/score_paid_task_listings.py`
- `tests/unit/sales/`
- `tests/unit/scripts/test_agent_work_receipt_gate.py`
- `tests/unit/scripts/test_build_non_bounty_income_map.py`
- `tests/unit/scripts/test_build_paid_task_automation_plan.py`
- `tests/unit/scripts/test_check_commercial_mesh_platform_readiness.py`
- `tests/unit/scripts/test_collect_paid_task_listings.py`
- `tests/unit/scripts/test_ensure_x402_paid_api_public.py`
- `tests/unit/scripts/test_run_income_watch_cycle.py`
- `tests/unit/scripts/test_run_paid_task_hunter.py`
- `tests/unit/scripts/test_run_paid_task_watch_loop.py`
- `tests/unit/scripts/test_score_paid_task_listings.py`

## Do

- Run commercial sales and paid-task unit tests.
- Verify commercial static readiness with claim boundaries.
- Build local paid-task and non-bounty income artifacts under `.tmp`.
- Provide an offline income-watch mode that validates command wiring without
  marketplace polling, wallet probes, or submission scripts.
- Keep funds-received and settlement claims fail-closed.

## Do Not

- Submit to external marketplaces, send outreach, charge buyers, register
  listings, or probe private wallets as a claimed success.
- Store private keys, seed phrases, bot tokens, raw customer data, or payment
  secrets.
- Treat static readiness as production revenue evidence.

## Verification

```bash
python3 -m py_compile src/sales/*.py scripts/ops/*agent*.py scripts/ops/*paid*.py scripts/ops/*income*.py
PYTHONPATH=. ./.venv/bin/pytest tests/unit/sales tests/unit/scripts/test_run_income_watch_cycle.py tests/unit/scripts/test_run_paid_task_hunter.py tests/unit/scripts/test_check_commercial_mesh_platform_readiness.py tests/unit/scripts/test_agent_work_receipt_gate.py -q --no-cov
PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_build_non_bounty_income_map.py tests/unit/scripts/test_build_paid_task_automation_plan.py tests/unit/scripts/test_collect_paid_task_listings.py tests/unit/scripts/test_ensure_x402_paid_api_public.py tests/unit/scripts/test_run_paid_task_watch_loop.py tests/unit/scripts/test_score_paid_task_listings.py -q --no-cov
PYTHONPATH=. ./.venv/bin/python scripts/ops/check_commercial_mesh_platform_readiness.py --require-ready --json
PYTHONPATH=. ./.venv/bin/python scripts/ops/build_paid_task_automation_plan.py --write-md .tmp/validation-shards/commercial-income/paid-task-automation-plan.md --write-json .tmp/validation-shards/commercial-income/paid-task-automation-plan.json
PYTHONPATH=. ./.venv/bin/python scripts/ops/build_non_bounty_income_map.py --write-md .tmp/validation-shards/commercial-income/non-bounty-income-map.md --write-json .tmp/validation-shards/commercial-income/non-bounty-income-map.json --artifact-dir .tmp/validation-shards/commercial-income/non-bounty-artifacts
PYTHONPATH=. ./.venv/bin/python scripts/ops/run_income_watch_cycle.py --offline --cycles 1 --agentjob-wait-seconds 0 --output .tmp/validation-shards/commercial-income/income-watch-cycle-offline.json --history-jsonl .tmp/validation-shards/commercial-income/income-watch-history-offline.jsonl
PYTHONPATH=. ./.venv/bin/python scripts/ops/score_paid_task_listings.py --input docs/commercial/paid_task_listings.example.json --top 5 --write-json .tmp/validation-shards/commercial-income/paid-task-score-example.json --write-md .tmp/validation-shards/commercial-income/paid-task-score-example.md
find .tmp/validation-shards/commercial-income -name '*.json' -print0 | xargs -0 -I{} python3 -m json.tool {} >/dev/null
```

