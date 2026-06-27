# Production Raw Evidence Operator Packet Index

Generated: `2026-05-20T22:31:09Z`
Decision: `RAW_EVIDENCE_OPERATOR_PACKET_ACTIONABLE`
Local handoff complete: `True`
Production ready: `False`
Raw readiness decision: `BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE`
Raw readiness ready for collectors: `False`

## Claim Boundary

Read-only operator packet index for raw production evidence replacement. It lists required operator bundle files and commands, but does not create production evidence, run collectors, contact live systems, mutate runtime state, or mark /goal complete.

## Collectors

- `stable-deploy`: files=`6`, production_ready=`0`, replacement_required=`6`
  - replace `.tmp/production-raw-evidence-operator-bundle/stable-deploy/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/stable-deploy/argocd-app.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/stable-deploy/kubernetes-runtime-health.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/stable-deploy/deployment-smoke.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/stable-deploy/image-provenance.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/stable-deploy/rollback-restore-drill.json`
- `self-healing-pqc-mesh`: files=`8`, production_ready=`0`, replacement_required=`8`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/peer-discovery-membership.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/pqc-handshake-transport.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/failover-recovery-run.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/hostile-network-chaos.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/mapek-action-log.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/telemetry-slo-report.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/self-healing-pqc-mesh/traffic-integrity-boundary.json`
- `zero-trust-pqc`: files=`8`, production_ready=`0`, replacement_required=`8`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/production-spire-ha-federation.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/mtls-fail-closed.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/pqc-hybrid-tls-handshake.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/ca-key-rotation.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/identity-policy-enforcement.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/session-lifecycle-load.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/zero-trust-pqc/customer-traffic-boundary.json`
- `ebpf-observability`: files=`7`, production_ready=`0`, replacement_required=`7`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/live-xdp-attach.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/dmesg-bpf-clean.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/pps-benchmark.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/prometheus-scrape.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/grafana-alert-drill.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/ebpf-observability/rollout-coverage.json`
- `signed-release-provenance`: files=`8`, production_ready=`0`, replacement_required=`8`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/github-run.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/signed-artifacts.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/rekor-entries.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/certificates.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/slsa-attestations.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/cosign-verify.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/signed-release-provenance/bundle-retention.json`
- `billing-provisioning`: files=`6`, production_ready=`0`, replacement_required=`6`
  - replace `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/payment-webhook.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/activation-flow.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/revocation-flow.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/provisioning-side-effects.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/billing-provisioning/billing-db-migration-rollback.json`
- `sla-telemetry`: files=`6`, production_ready=`0`, replacement_required=`6`
  - replace `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/prometheus-query-results.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/grafana-dashboard-snapshot.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/client-sla-report.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/alert-drill.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/sla-telemetry/error-budget.json`
- `paid-client-serviceability`: files=`8`, production_ready=`0`, replacement_required=`8`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/billing-webhook-replay.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/paid-activation-revocation.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/customer-access-matrix.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/customer-sla-report.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/restore-rehearsal.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/signed-update-rollback.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/paid-client-serviceability/support-incident-drill.json`
- `live-rollout`: files=`6`, production_ready=`0`, replacement_required=`6`
  - replace `.tmp/production-raw-evidence-operator-bundle/live-rollout/operator-manifest.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/live-rollout/argocd-app-get.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/live-rollout/kubectl-rollout-status.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/live-rollout/rollback-drill.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/live-rollout/admission-allow-deny.json`
  - replace `.tmp/production-raw-evidence-operator-bundle/live-rollout/image-digests.json`

## Summary

```json
{
  "actionable_packets": 9,
  "collectors_total": 9,
  "collectors_with_replacements_required": 9,
  "local_entrypoints_missing": 0,
  "operator_bundle_files_existing": 63,
  "operator_bundle_files_production_ready": 0,
  "operator_bundle_files_replacement_required": 63,
  "packets_total": 9,
  "production_ready_blocked_by_raw_readiness": false,
  "raw_files_total": 63,
  "raw_readiness_collectors_blocked": 9,
  "raw_readiness_collectors_ready": 0,
  "raw_readiness_collectors_total": 9,
  "raw_readiness_decision": "BLOCKED_ON_OPERATOR_PRODUCTION_EVIDENCE",
  "raw_readiness_raw_files_local_observation": 63,
  "raw_readiness_raw_files_ready": 0,
  "raw_readiness_raw_files_total": 63,
  "raw_readiness_ready_for_collectors": false
}
```
