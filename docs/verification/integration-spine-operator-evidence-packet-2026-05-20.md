# Integration Spine Operator Evidence Packet

Generated: `2026-05-21T08:03:51Z`
Decision: `OPERATOR_ACTION_REQUIRED`
Selected evidence key: `external_settlement`

## Claim Boundary

Read-only operator packet for the next integration-spine production evidence blocker. It does not collect evidence, write evidence files, submit transactions, contact live systems, mutate NL/SPB/runtime state, or mark the objective complete.

## Required Artifacts

- `.tmp/external-settlement-evidence/settlement-submit.json` - retained submitted X0T settlement receipt - exists: `False`
- `.tmp/validation-shards/x0t-external-settlement-evidence-current.json` - retained receipt schema gate output - exists: `True`
- `.tmp/validation-shards/x0t-external-settlement-live-rpc-current.json` - live read-only Base RPC receipt verification output - exists: `True`
- `.tmp/validation-shards/x0t-external-settlement-current-blocker-current.json` - combined external settlement blocker gate output - exists: `True`

## Required Fields

- status or evidence_status == VERIFIED HERE
- settlement_submitted == true
- destination_chain is base-sepolia/base_sepolia or base-mainnet/base
- settlement_id is specific and non-placeholder
- token_symbol == X0T
- transaction_receipt_status indicates a successful mined receipt
- block_number is positive
- block_hash is a 0x-prefixed 32-byte hash
- from_address and to_address are 0x-prefixed 20-byte addresses
- transaction_hash is a 0x-prefixed 32-byte hash
- source_commands contains at least two exact retained commands and includes the exact transaction hash
- explorer_url is HTTPS, matches destination_chain, and contains the exact transaction hash
- packet_hash is a 64-character lowercase hex digest matching the canonical receipt payload
- template_only is absent or false

## Commands

- `python3 scripts/ops/scaffold_x0t_external_settlement_evidence.py --write-template-files --force`
  - purpose: render template-only external settlement intake files for the operator; these templates are not production evidence
  - existing entrypoint: `True`
- `export X0T_BASE_RPC_URL='<read-only Base RPC URL for the matching chain>'`
  - purpose: operator input; not evidence by itself
  - existing entrypoint: `True`
- `export X0T_SETTLEMENT_TX_HASH='<0x-prefixed submitted settlement transaction hash>'`
  - purpose: operator input; not evidence by itself
  - existing entrypoint: `True`
- `export X0T_DESTINATION_CHAIN='<base-sepolia|base|base-mainnet>'`
  - purpose: operator input; must match the RPC URL and submitted transaction chain
  - existing entrypoint: `True`
- `export X0T_SETTLEMENT_ID='<non-placeholder settlement id>'`
  - purpose: operator input; not evidence by itself
  - existing entrypoint: `True`
- `python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --transaction-hash "$X0T_SETTLEMENT_TX_HASH" --destination-chain "$X0T_DESTINATION_CHAIN" --settlement-id "$X0T_SETTLEMENT_ID" --rpc-url "$X0T_BASE_RPC_URL" --evidence .tmp/external-settlement-evidence/settlement-submit.json --require-preflight-ready`
  - purpose: validate capture inputs without calling RPC or writing settlement evidence
  - existing entrypoint: `True`
- `python3 -m src.integration.external_settlement --root . --capture-from-rpc --transaction-hash "$X0T_SETTLEMENT_TX_HASH" --destination-chain "$X0T_DESTINATION_CHAIN" --settlement-id "$X0T_SETTLEMENT_ID" --rpc-url "$X0T_BASE_RPC_URL" --evidence .tmp/external-settlement-evidence/settlement-submit.json --write-evidence --require-ready`
  - purpose: capture retained receipt from live read-only RPC and validate it
  - existing entrypoint: `True`
- `python3 scripts/ops/verify_x0t_external_settlement_evidence.py --evidence .tmp/external-settlement-evidence/settlement-submit.json --require-ready`
  - purpose: rerun retained settlement evidence schema gate
  - existing entrypoint: `True`
- `python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --evidence .tmp/external-settlement-evidence/settlement-submit.json --rpc-url "$X0T_BASE_RPC_URL" --require-ready`
  - purpose: rerun retained settlement evidence plus live read-only RPC gate
  - existing entrypoint: `True`
- `python3 -m src.integration.evidence_source_candidates --root . --require-ready`
  - purpose: rerun source-candidate audit
  - existing entrypoint: `True`
- `python3 -m src.integration.production_evidence_replacement_passport --root . --verification-output-json .tmp/validation-shards/integration-spine-production-evidence-replacement-passport-verification-current.json --require-valid --require-ready`
  - purpose: rerun production evidence replacement passport
  - existing entrypoint: `True`
- `python3 -m src.integration.production_evidence_intake --root . --require-ready`
  - purpose: rerun production evidence intake gate
  - existing entrypoint: `True`
- `python3 -m src.integration.production_input_return_acceptance --root . --require-ready`
  - purpose: rerun production input return acceptance after intake
  - existing entrypoint: `True`
- `python3 -m src.integration.production_input_pipeline --root . --require-ready`
  - purpose: rerun production input pipeline before closeout review
  - existing entrypoint: `True`
- `python3 -m src.integration.production_closeout_review --root . --require-ready`
  - purpose: rerun production closeout review before final completion audit
  - existing entrypoint: `True`
- `python3 -m src.integration.completion_audit --root . --require-complete`
  - purpose: rerun completion audit
  - existing entrypoint: `True`
- `python3 -m src.integration.production_gap_index --root . --require-clear`
  - purpose: rerun production gap index
  - existing entrypoint: `True`

## Acceptance Checks

- x0t_external_settlement_ready == true
- live_rpc_ready == true
- verify_x0t_external_settlement_evidence.py reports READY
- verify_x0t_external_settlement_live_rpc.py reports READY
- source-candidate audit marks external_settlement READY_TO_INSTALL
- production evidence replacement passport is PRODUCTION_EVIDENCE_REPLACEMENT_PASSPORT_CLEAR
- production evidence intake no longer lists external_settlement in pending_evidence_keys
- production input pipeline reports READY_FOR_PRODUCTION_CLOSEOUT_REVIEW

## Fail-Closed Rules

- Do not synthesize transaction hashes, block hashes, explorer URLs, or source commands.
- Do not mark settlement ready from a non-live or mismatched RPC report.
- Do not use template/example settlement-submit.json as evidence.
- Do not treat external settlement scaffold templates as production evidence.
- Do not mutate NL/SPB/VPN runtime from this packet.

## All Blocker Packets

### external_settlement

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `external_settlement`
- required artifacts: `4`
- commands: `17`
- missing entrypoints: `0`

Current blockers:
- retained submitted settlement receipt is missing
- live Base RPC settlement verification is not ready
- semantic blockers still open for external-settlement: 1
- retained submitted settlement receipt is missing
- live Base RPC settlement verification is not ready
- semantic blockers still open for external-settlement: 1
- retained submitted settlement receipt is missing
- live Base RPC settlement verification is not ready
- ... 1 more

### billing-provisioning

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `6`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/payment-webhook.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/payment-webhook.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- ... 10 more

### ebpf-observability

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `7`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: source_commands must not contain placeholders
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: template/mock/placeholder markers must be absent
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/live-xdp-attach.json: source_commands must not contain placeholders
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: source_commands must not contain placeholders
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: template/mock/placeholder markers must be absent
- .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: production_ready must be true for source-candidate promotion
- ... 23 more

### live_spire_mtls

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `8`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/production-spire-ha-federation.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/production-spire-ha-federation.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- ... 22 more

### multi_host_mesh

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `8`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/peer-discovery-membership.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/peer-discovery-membership.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- ... 22 more

### paid_client_path

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `8`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/billing-webhook-replay.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/billing-webhook-replay.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- ... 15 more

### safe_rollout_rollback

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `6`
- commands: `17`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/live-rollout/argocd-app-get.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/live-rollout/argocd-app-get.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- ... 16 more

### signed-release-provenance

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `8`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: source_commands must not contain placeholders
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: template/mock/placeholder markers must be absent
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: source_commands must not contain placeholders
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: template/mock/placeholder markers must be absent
- .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: production_ready must be true for source-candidate promotion
- ... 31 more

### sla-telemetry

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `6`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/prometheus-query-results.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/prometheus-query-results.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/grafana-dashboard-snapshot.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/sla-telemetry/prometheus-query-results.json: production_ready must be true for source-candidate promotion
- ... 9 more

### stable-deploy

- decision: `OPERATOR_ACTION_REQUIRED`
- actionable: `True`
- packet kind: `raw_production_bundle`
- required artifacts: `6`
- commands: `15`
- missing entrypoints: `0`

Current blockers:
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/argocd-app.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/argocd-app.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: production_ready must be true for source-candidate promotion
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: production_promotion_blockers must be empty
- .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: claim_boundary/environment still describes local, staging, test, or simulation context
- ... 15 more
