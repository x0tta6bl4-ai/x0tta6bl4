# X0T External Settlement Gate

Generated: `2026-05-20`
Status: `VERIFIED HERE`

## Scope

The external settlement gate validates retained evidence for an already-submitted X0T settlement transaction. It is read-only: it does not submit transactions, mutate chain state, mutate VPN/runtime state, or mark the integration objective complete.
The capture preflight mode validates operator inputs without calling RPC providers or writing the retained receipt.

## Evidence Contract

Required retained input:

- `.tmp/external-settlement-evidence/settlement-submit.json`

The retained receipt must include:

- `status` or `evidence_status`: `VERIFIED HERE`
- `settlement_submitted`: `true`
- `destination_chain`: `base-sepolia`, `base_sepolia`, `base-mainnet`, or `base`
- `settlement_id`: non-placeholder settlement id
- `token_symbol`: `X0T`
- mined successful receipt fields: `transaction_hash`, `transaction_receipt_status`, `block_number`, `block_hash`, `from_address`, `to_address`
- at least two retained `source_commands`, with the exact transaction hash in the commands
- HTTPS `explorer_url` containing the exact transaction hash and matching the destination chain explorer host
- lowercase 64-character `packet_hash` matching the canonical receipt payload
- `template_only`: not `true`

## Current Result

The current repository state is still blocked because operator capture inputs have not passed read-only preflight, the retained receipt file is missing, and no live Base RPC verification can run without it.

Current generated reports:

- `.tmp/validation-shards/x0t-external-settlement-capture-preflight-current.json`
- `.tmp/validation-shards/x0t-external-settlement-evidence-current.json`
- `.tmp/validation-shards/x0t-external-settlement-live-rpc-current.json`
- `.tmp/validation-shards/x0t-external-settlement-current-blocker-current.json`
- `.tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json`

Current decision:

- `BLOCKED_ON_REAL_SETTLEMENT_RECEIPT`
- `X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR`

Current operator handoff summary:

- `capture_preflight_decision=CAPTURE_INPUTS_BLOCKED`
- `capture_inputs_ready=false`
- `missing_inputs_total=5`
- `operator_actions_total=6`
- `operator_commands_total=5`
- `operator_command_entrypoints_missing=0`
- `operator_command_surface_ready=true`
- `operator_commands_with_shell_redirection_placeholders=0`
- `operator_command_shell_surface_ready=true`

## Verified Commands

```bash
python3 -m py_compile src/integration/external_settlement.py tests/unit/test_integration_external_settlement.py
python3 -m py_compile src/integration/external_settlement_operator_handoff.py tests/unit/test_integration_external_settlement_operator_handoff.py
pytest tests/unit/test_integration_external_settlement.py tests/unit/test_integration_completion_audit.py tests/unit/test_integration_spine.py -q --no-cov
python3 -m pytest tests/unit/test_integration_external_settlement_operator_handoff.py -q --no-cov
python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --transaction-hash "" --destination-chain base-sepolia --settlement-id "" --rpc-url "" --require-preflight-ready
python3 -m src.integration.external_settlement --root . --require-ready
python3 -m src.integration.external_settlement_operator_handoff --root . --require-ready
```

The `--require-preflight-ready` command is expected to return exit code `2` until operator capture inputs are supplied. The `--require-ready` command is expected to return exit code `2` until real retained receipt evidence and live RPC verification are available. The operator handoff command is also expected to return exit code `2` while any capture, retained receipt, live-RPC, import, or completion-gate input remains blocked.
