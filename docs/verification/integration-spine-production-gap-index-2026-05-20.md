# Integration Spine Production Gap Index

Generated: `2026-05-21T16:09:06Z`
Decision: `BLOCKED_ON_OPERATOR_EVIDENCE`
Goal can be marked complete: `False`

## Claim Boundary

Read-only production evidence gap index. It reads existing next-input, import, completion-audit, production-intake, governance handoff, external-settlement handoff, and rollout provenance artifacts; it does not collect live evidence, stage files, submit settlement transactions, mutate runtime state, or close /goal.

## Summary

- required evidence keys: `10`
- ready evidence keys: `0`
- pending evidence keys: `10`
- missing source artifacts: `1`
- blocked source artifacts: `9`
- route missing: `0`
- import mismatches: `0`
- completion audit clear: `False`
- completion checklist: `44/54 passed`, `10 blocking`
- local wiring passed: `True`
- production readiness passed: `False`
- raw readiness decision: `BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE`
- raw readiness files: `0/63 ready`, `63 local observation`
- governance execute decision: `READY_TO_EXECUTE`
- governance execute handoff: `X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL`
- governance handoff actionable: `True`
- governance proposal executed: `False`
- governance handoff commands: `5 commands`, `0 missing`, `0 shell placeholders`, `sequence_ready=True`
- X0T bridge config: `X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR`
- X0T contract readiness: `BLOCKED_ON_DEPLOYMENT_CONFIG`
- X0T contract deployment ready: `False`
- X0T contract operator handoff: `X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR`
- external settlement handoff: `X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR`
- external settlement handoff clear: `True`
- external settlement capture preflight: `CAPTURE_INPUTS_BLOCKED`
- external settlement handoff commands: `5 commands`, `0 missing`, `0 shell placeholders`
- live rollout handoff: `LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR`
- live rollout ready for completion rerun: `False`
- live rollout handoff commands: `4 commands`, `0 missing`, `0 shell placeholders`

## X0T Contract Deployment Operator Handoff

- decision: `X0T_CONTRACT_DEPLOYMENT_CONFIG_BLOCKED_ON_OPERATOR`
- deployment ready: `False`
- contract readiness: `BLOCKED_ON_DEPLOYMENT_CONFIG`
- bridge config: `X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR`
- approval value required: `apply-bridge-address-base-sepolia`

### Missing Inputs

- `operator_contract_addresses` - `OPERATOR_INPUT_REQUIRED`
  reason: operator bridge config still needs its own deployed bridge contract address; do not substitute X0TToken or MeshGovernance
  command: `export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"`
  command: `python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready`
  command: `X0T_APPLY_BRIDGE_ADDRESS_APPROVAL=apply-bridge-address-base-sepolia python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready`
  command: `python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md`

### Next Actions

1. `provide_bridge_address` - `OPERATOR_INPUT_REQUIRED`
   command: `export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"`
   submits transaction: `False`
2. `validate_bridge_address` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready`
   submits transaction: `False`
3. `apply_bridge_address_with_operator_approval` - `OPERATOR_APPROVAL_REQUIRED`
   command: `X0T_APPLY_BRIDGE_ADDRESS_APPROVAL=apply-bridge-address-base-sepolia python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready`
   requires operator approval: `True`
   submits transaction: `False`
4. `rerun_contract_readiness` - `AFTER_APPLY`
   command: `python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md`
   submits transaction: `False`
5. `rerun_completion_audit` - `AFTER_APPLY`
   command: `python3 -m src.integration.completion_audit --root . --output-json .tmp/validation-shards/integration-spine-completion-audit-current.json --output-md docs/verification/integration-spine-completion-audit-2026-05-20.md`
   submits transaction: `False`
6. `rerun_production_gap_index` - `AFTER_APPLY`
   command: `python3 -m src.integration.production_gap_index --root . --output-json .tmp/validation-shards/integration-spine-production-gap-index-current.json --output-md docs/verification/integration-spine-production-gap-index-2026-05-20.md`
   submits transaction: `False`

### Command Surface

- `validate_bridge_address` - `READY`
  entrypoint: `scripts/ops/apply_x0t_bridge_contract_address.py` exists=`True`
- `apply_bridge_address_with_operator_approval` - `READY`
  entrypoint: `scripts/ops/apply_x0t_bridge_contract_address.py` exists=`True`
- `rerun_contract_readiness` - `READY`
  entrypoint: `scripts/ops/check_x0t_contract_readiness.py` exists=`True`
- `rerun_completion_audit` - `READY`
  entrypoint: `src/integration/completion_audit.py` exists=`True`
- `rerun_production_gap_index` - `READY`
  entrypoint: `src/integration/production_gap_index.py` exists=`True`

## X0T Governance Execute Operator Handoff

- decision: `X0T_GOVERNANCE_EXECUTE_HANDOFF_READY_FOR_OPERATOR_APPROVAL`
- actionable: `True`
- ready for operator execute: `True`
- readiness decision: `READY_TO_EXECUTE`
- execute ready now: `True`
- approval value required: `execute-proposal-1-base-sepolia`

### Missing Inputs

- `explicit_operator_approval` - `OPERATOR_APPROVAL_REQUIRED`
  reason: execute_dao_proposal.py refuses to submit without this proposal-specific value
- `operator_private_key` - `OPERATOR_INPUT_REQUIRED`
  reason: execute transaction signing requires an operator-supplied key

### Next Actions

1. `refresh_readiness` - `DONE`
   command: `python3 scripts/ops/check_x0t_governance_execute_readiness.py --write-json --write-md`
   submits transaction: `False`
2. `dry_run_execute_boundary` - `READY`
   command: `python3 execute_dao_proposal.py --dry-run`
   submits transaction: `False`
3. `execute_with_operator_approval` - `OPERATOR_APPROVAL_REQUIRED`
   command: `X0T_EXECUTE_PROPOSAL_APPROVAL=execute-proposal-1-base-sepolia PRIVATE_KEY="$PRIVATE_KEY" python3 execute_dao_proposal.py`
   requires operator approval: `True`
   submits transaction: `True`
4. `retain_execution_receipt` - `AFTER_EXECUTE`
   artifact: `.tmp/validation-shards/x0t-governance-execute-proposal-1-receipt-current.json`
   acceptance: receipt ok=true only when tx receipt status is 1 and final proposal state is Executed
5. `rerun_completion_and_gap` - `AFTER_EXECUTE`
   command: `python3 -m src.integration.completion_audit --root . --output-json .tmp/validation-shards/integration-spine-completion-audit-current.json --output-md docs/verification/integration-spine-completion-audit-2026-05-20.md`
   command: `python3 -m src.integration.production_gap_index --root . --output-json .tmp/validation-shards/integration-spine-production-gap-index-current.json --output-md docs/verification/integration-spine-production-gap-index-2026-05-20.md`
   submits transaction: `False`

### Command Surface

- `refresh_readiness` - `READY`
  entrypoint: `scripts/ops/check_x0t_governance_execute_readiness.py` exists=`True`
- `dry_run_execute_boundary` - `READY`
  entrypoint: `execute_dao_proposal.py` exists=`True`
- `execute_with_operator_approval` - `READY`
  entrypoint: `execute_dao_proposal.py` exists=`True`
- `rerun_completion_and_gap` - `READY`
  entrypoint: `src/integration/completion_audit.py` exists=`True`
- `rerun_completion_and_gap` - `READY`
  entrypoint: `src/integration/production_gap_index.py` exists=`True`

## External Settlement Operator Handoff

- decision: `X0T_EXTERNAL_SETTLEMENT_HANDOFF_BLOCKED_ON_OPERATOR`
- ready for completion rerun: `False`
- capture preflight: `CAPTURE_INPUTS_BLOCKED`
- capture inputs ready: `False`

### Missing Inputs

- `capture_input_preflight` - `OPERATOR_INPUT_REQUIRED`
  reason: operator capture inputs have not passed read-only preflight
  command: `python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --transaction-hash "$X0T_SETTLEMENT_TX_HASH" --destination-chain "$X0T_DESTINATION_CHAIN" --settlement-id "$X0T_SETTLEMENT_ID" --rpc-url "$X0T_BASE_RPC_URL" --require-preflight-ready`
- `retained_settlement_receipt` - `OPERATOR_INPUT_REQUIRED`
  reason: retained settlement receipt is missing or invalid
  artifact: `.tmp/external-settlement-evidence/settlement-submit.json`
- `live_rpc_receipt_verification` - `OPERATOR_INPUT_REQUIRED`
  reason: retained receipt has not passed live Base RPC verification
  command: `python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready --rpc-url "$X0T_BASE_RPC_URL"`
- `production_evidence_import` - `OPERATOR_INPUT_REQUIRED`
  reason: production evidence import is not complete
  command: `python3 scripts/ops/run_integration_spine_production_input_pipeline.py --require-ready`
- `completion_gate_external_settlement` - `OPERATOR_INPUT_REQUIRED`
  reason: completion gate still reports external settlement as not ready
  command: `python3 scripts/ops/run_integration_spine_completion_gate.py --require-complete`

### Next Actions

1. `preflight_capture_inputs` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 -m src.integration.external_settlement --root . --preflight-capture-inputs --transaction-hash "$X0T_SETTLEMENT_TX_HASH" --destination-chain "$X0T_DESTINATION_CHAIN" --settlement-id "$X0T_SETTLEMENT_ID" --rpc-url "$X0T_BASE_RPC_URL" --require-preflight-ready`
2. `capture_real_settlement_receipt` - `OPERATOR_INPUT_REQUIRED`
   description: Place a real submitted X0T transaction receipt at .tmp/external-settlement-evidence/settlement-submit.json.
3. `verify_retained_settlement_json` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 scripts/ops/verify_x0t_external_settlement_evidence.py --require-ready`
4. `verify_live_base_rpc` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 scripts/ops/verify_x0t_external_settlement_live_rpc.py --require-ready --rpc-url "$X0T_BASE_RPC_URL"`
5. `rerun_production_input_pipeline` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 scripts/ops/run_integration_spine_production_input_pipeline.py --require-ready`
6. `rerun_completion_gate` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 scripts/ops/run_integration_spine_completion_gate.py --require-complete`

### Command Surface

- `preflight_capture_inputs` - `READY`
  entrypoint: `src/integration/external_settlement.py` exists=`True`
- `verify_retained_settlement_json` - `READY`
  entrypoint: `scripts/ops/verify_x0t_external_settlement_evidence.py` exists=`True`
- `verify_live_base_rpc` - `READY`
  entrypoint: `scripts/ops/verify_x0t_external_settlement_live_rpc.py` exists=`True`
- `rerun_production_input_pipeline` - `READY`
  entrypoint: `scripts/ops/run_integration_spine_production_input_pipeline.py` exists=`True`
- `rerun_completion_gate` - `READY`
  entrypoint: `scripts/ops/run_integration_spine_completion_gate.py` exists=`True`

## Live Rollout Image Digest Operator Handoff

- decision: `LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR`
- rollout decision: `CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS`
- ready for completion rerun: `False`
- can close image digests blocker: `False`

### Missing Inputs

- `live_rollout_image_digest_provenance` - `OPERATOR_INPUT_REQUIRED`
  reason: runtime/deploy image references must be digest-pinned and backed by retained per-image cosign/SLSA provenance artifacts
  command: `python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force`
  command: `python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready`
  command: `python3 -m src.integration.rollout_provenance --root . --raw-image-digests .tmp/live-rollout-raw-evidence/image-digests.json --provenance-gate .tmp/validation-shards/deploy-image-provenance-gate-current.json --require-ready`
  command: `python3 -m src.integration.current_evidence_rollup --root . --require-complete`

### Next Actions

1. `render_template_pack` - `OPERATOR_INPUT_REQUIRED`
   command: `python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force`
2. `return_digest_pinned_evidence` - `OPERATOR_INPUT_REQUIRED`
3. `verify_live_rollout_evidence_gate` - `AFTER_OPERATOR_EVIDENCE`
   command: `python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready`
4. `rerun_rollout_provenance` - `AFTER_OPERATOR_EVIDENCE`
   command: `python3 -m src.integration.rollout_provenance --root . --raw-image-digests .tmp/live-rollout-raw-evidence/image-digests.json --provenance-gate .tmp/validation-shards/deploy-image-provenance-gate-current.json --require-ready`
5. `rerun_current_evidence_rollup` - `AFTER_ROLLOUT_READY`
   command: `python3 -m src.integration.current_evidence_rollup --root . --require-complete`

### Command Surface

- `render_template_pack` - `READY`
  entrypoint: `scripts/ops/scaffold_live_rollout_image_provenance_evidence.py` exists=`True`
- `verify_live_rollout_evidence_gate` - `READY`
  entrypoint: `scripts/ops/verify_live_rollout_evidence_gate.py` exists=`True`
- `rerun_rollout_provenance` - `READY`
  entrypoint: `src/integration/rollout_provenance.py` exists=`True`
- `rerun_current_evidence_rollup` - `READY`
  entrypoint: `src/integration/current_evidence_rollup.py` exists=`True`

## Operator Priority Order

1. `external_settlement` - `MISSING_SOURCE_ARTIFACT` at `.tmp/external-settlement-evidence/settlement-submit.json`
   action: Submit or locate a real external X0T settlement transaction, retain settlement-submit.json, verify it against live Base RPC, and rerun the retained evidence gates.
   verify: `python3 -m src.integration.external_settlement --require-ready --rpc-url <read-only Base RPC URL>`
   first blocker: retained submitted settlement receipt is missing
2. `billing-provisioning` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_billing_provisioning_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_billing_provisioning_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/billing-provisioning-raw-evidence/operator-manifest.json`
   - `.tmp/billing-provisioning-raw-evidence/payment-webhook.json`
   - `.tmp/billing-provisioning-raw-evidence/activation-flow.json`
   - `.tmp/billing-provisioning-raw-evidence/revocation-flow.json`
   - `.tmp/billing-provisioning-raw-evidence/provisioning-side-effects.json`
   - `... 1 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json: production_ready must be true for source-candidate promotion
3. `ebpf-observability` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_ebpf_observability_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_ebpf_observability_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/ebpf-observability-raw-evidence/operator-manifest.json`
   - `.tmp/ebpf-observability-raw-evidence/live-xdp-attach.json`
   - `.tmp/ebpf-observability-raw-evidence/dmesg-bpf-clean.json`
   - `.tmp/ebpf-observability-raw-evidence/pps-benchmark.json`
   - `.tmp/ebpf-observability-raw-evidence/prometheus-scrape.json`
   - `... 2 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json: source_commands must not contain placeholders
4. `live_spire_mtls` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_zero_trust_pqc_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_zero_trust_pqc_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/zero-trust-pqc-raw-evidence/operator-manifest.json`
   - `.tmp/zero-trust-pqc-raw-evidence/production-spire-ha-federation.json`
   - `.tmp/zero-trust-pqc-raw-evidence/mtls-fail-closed.json`
   - `.tmp/zero-trust-pqc-raw-evidence/pqc-hybrid-tls-handshake.json`
   - `.tmp/zero-trust-pqc-raw-evidence/ca-key-rotation.json`
   - `... 3 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json: production_ready must be true for source-candidate promotion
5. `multi_host_mesh` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_self_healing_pqc_mesh_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_self_healing_pqc_mesh_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/self-healing-pqc-mesh-raw-evidence/operator-manifest.json`
   - `.tmp/self-healing-pqc-mesh-raw-evidence/peer-discovery-membership.json`
   - `.tmp/self-healing-pqc-mesh-raw-evidence/pqc-handshake-transport.json`
   - `.tmp/self-healing-pqc-mesh-raw-evidence/failover-recovery-run.json`
   - `.tmp/self-healing-pqc-mesh-raw-evidence/hostile-network-chaos.json`
   - `... 3 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json: production_ready must be true for source-candidate promotion
6. `paid_client_path` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_paid_client_serviceability_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_paid_client_serviceability_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/paid-client-serviceability-raw-evidence/operator-manifest.json`
   - `.tmp/paid-client-serviceability-raw-evidence/billing-webhook-replay.json`
   - `.tmp/paid-client-serviceability-raw-evidence/paid-activation-revocation.json`
   - `.tmp/paid-client-serviceability-raw-evidence/customer-access-matrix.json`
   - `.tmp/paid-client-serviceability-raw-evidence/customer-sla-report.json`
   - `... 3 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json: production_ready must be true for source-candidate promotion
7. `safe_rollout_rollback` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_live_rollout_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/live-rollout-raw-evidence/operator-manifest.json`
   - `.tmp/live-rollout-raw-evidence/argocd-app-get.json`
   - `.tmp/live-rollout-raw-evidence/kubectl-rollout-status.json`
   - `.tmp/live-rollout-raw-evidence/rollback-drill.json`
   - `.tmp/live-rollout-raw-evidence/admission-allow-deny.json`
   - `... 1 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json: production_ready must be true for source-candidate promotion
8. `signed-release-provenance` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_signed_release_provenance_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_signed_release_provenance_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/signed-release-provenance-raw-evidence/operator-manifest.json`
   - `.tmp/signed-release-provenance-raw-evidence/github-run.json`
   - `.tmp/signed-release-provenance-raw-evidence/signed-artifacts.json`
   - `.tmp/signed-release-provenance-raw-evidence/rekor-entries.json`
   - `.tmp/signed-release-provenance-raw-evidence/certificates.json`
   - `... 3 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json: source_commands must not contain placeholders
9. `sla-telemetry` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_sla_telemetry_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_sla_telemetry_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/sla-telemetry-raw-evidence/operator-manifest.json`
   - `.tmp/sla-telemetry-raw-evidence/prometheus-query-results.json`
   - `.tmp/sla-telemetry-raw-evidence/grafana-dashboard-snapshot.json`
   - `.tmp/sla-telemetry-raw-evidence/client-sla-report.json`
   - `.tmp/sla-telemetry-raw-evidence/alert-drill.json`
   - `... 1 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json: production_ready must be true for source-candidate promotion
10. `stable-deploy` - `SOURCE_ARTIFACT_BLOCKED` at `.tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json`
   action: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
   collector: `python3 scripts/ops/collect_stable_deploy_evidence_bundle.py --require-ready`
   verify: `python3 scripts/ops/verify_stable_deploy_evidence_gate.py --require-ready`
   raw files to replace:
   - `.tmp/stable-deploy-raw-evidence/operator-manifest.json`
   - `.tmp/stable-deploy-raw-evidence/argocd-app.json`
   - `.tmp/stable-deploy-raw-evidence/kubernetes-runtime-health.json`
   - `.tmp/stable-deploy-raw-evidence/deployment-smoke.json`
   - `.tmp/stable-deploy-raw-evidence/image-provenance.json`
   - `... 1 more`
   first blocker: .tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json: production_ready must be true for source-candidate promotion

## Blocking Reasons

- X0T governance proposal is not executed
- Live rollout image digest/provenance handoff is not ready for completion rerun
- X0T contract deployment config is not ready
- one or more required source artifacts are missing
- one or more source artifacts exist but their evidence gates are blocked
- completion audit is not COMPLETE

## Required Next Evidence

- live_rollout_handoff: follow the image digest/provenance operator handoff, return digest-pinned runtime image evidence with retained provenance, then rerun rollout provenance and current rollup.
- x0t_governance: follow the read-only execute operator handoff, execute proposal 1 only with explicit operator approval when state is Ready, and retain final Executed-state evidence.
- x0t_contract: provide and apply the deployed Base Sepolia bridge contract address with the approved read-only/config-only bridge-config operator path, then rerun contract readiness and completion audit.
- external_settlement: Submit or locate a real external X0T settlement transaction, retain settlement-submit.json, verify it against live Base RPC, and rerun the retained evidence gates.
- billing-provisioning: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- ebpf-observability: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- live_spire_mtls: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- multi_host_mesh: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- paid_client_path: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- safe_rollout_rollback: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- signed-release-provenance: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- sla-telemetry: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.
- stable-deploy: Replace every listed retained/local raw file with operator-captured production JSON, including production_ready=true and no production_promotion_blockers, then rerun collectors and gates.

## Source Artifacts

- `.tmp/validation-shards/integration-spine-production-next-inputs-current.json`
- `.tmp/validation-shards/integration-spine-production-evidence-import-current.json`
- `.tmp/validation-shards/integration-spine-completion-audit-current.json`
- `.tmp/validation-shards/integration-spine-production-evidence-intake-current.json`
- `.tmp/validation-shards/x0t-governance-execute-proposal-1-readiness-current.json`
- `.tmp/validation-shards/x0t-governance-execute-operator-handoff-current.json`
- `.tmp/validation-shards/x0t-external-settlement-operator-handoff-current.json`
- `.tmp/validation-shards/live-rollout-image-digests-closure-attempt-current.json`
