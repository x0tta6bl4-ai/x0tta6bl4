# SOC2 Production Hardening Playbook

This playbook operationalizes the v1.1 hardening controls for x0tta6bl4 MaaS and is intended for on-call responders, platform SREs, and compliance reviewers.

## Scope

- PQC key compromise and emergency rotation
- Tamper-evident audit log preservation
- Tenant isolation validation
- PagerDuty escalation and post-incident evidence collection

## Control map

- Tamper-evident audit logs: [agent/internal/security/zerotrust.go](/mnt/projects/agent/internal/security/zerotrust.go)
- PQC rotation policy and overlap window: [agent/internal/crypto/pqc/rotation.go](/mnt/projects/agent/internal/crypto/pqc/rotation.go)
- PQC key sealing and namespaces: [k8s/secrets-pqc-keys.yaml](/mnt/projects/k8s/secrets-pqc-keys.yaml)
- Daily rotation automation: [k8s/cronjob-key-rotation.yaml](/mnt/projects/k8s/cronjob-key-rotation.yaml)
- Multi-tenant isolation values: [values-enterprise.yaml](/mnt/projects/charts/multi-tenant/values-enterprise.yaml)
- Production dashboards: [PQC Performance.json](/mnt/projects/observability/dashboards/PQC%20Performance.json), [eBPF Telemetry.json](/mnt/projects/observability/dashboards/eBPF%20Telemetry.json), [SLO Error Budget.json](/mnt/projects/observability/dashboards/SLO%20Error%20Budget.json)
- Evidence matrix: [evidence-matrix.md](/mnt/projects/compliance/soc2/evidence-matrix.md)

## Verification boundaries

- `VERIFIED HERE`: commands or script checks executed in the current repository environment and recorded in [v1.1-hardening-status.md](/mnt/projects/docs/verification/v1.1-hardening-status.md)
- `VERIFIED VIA SCRIPT/CI`: reproducible commands or CI jobs that are present in the repo but were not executed in this environment
- `NOT VERIFIED YET`: claims that still require a real cluster, real OIDC token, Rekor response, or measured performance run

## Severity model

- `SEV-1`: active key compromise, cross-tenant access, or audit-chain tampering
- `SEV-2`: failed scheduled rotation, eBPF loader degraded, or incomplete audit shipping
- `SEV-3`: dashboard alert drift or backup key escrow mismatch without active abuse

## RTO targets

- Key compromise containment: `< 1 hour`
- Compromised tenant isolation verification: `< 30 minutes`
- Audit chain export and evidence freeze: `< 15 minutes`

## PagerDuty routing

- Service: `x0tta6bl4-prod-security`
- Primary escalation: Platform Security
- Secondary escalation: Mesh SRE
- Tertiary escalation: Compliance Owner
- Required incident links:
  - Runbook: `https://docs.x0tta6bl4.io/runbooks/key-compromise`
  - Dashboard: `https://grafana.x0tta6bl4.io/d/pqc-performance`
  - Audit vault: `s3://x0tta6bl4-audit-worm/`

## SEV-1: PQC key compromise

### 0 to 15 minutes

1. Trigger PagerDuty `SEV-1` and freeze deployment changes.
2. Export the latest audit records from the tamper-evident log directory managed by [agent/internal/security/zerotrust.go](/mnt/projects/agent/internal/security/zerotrust.go).
3. Identify the affected tenant namespace and PQC key namespace from [values-enterprise.yaml](/mnt/projects/charts/multi-tenant/values-enterprise.yaml).
4. Disable external ingress for the impacted tenant with the tenant isolation chart or a temporary `CiliumNetworkPolicy`.

### 15 to 30 minutes

1. Force rotation by running the CronJob manually:
   ```bash
   kubectl -n x0tta6bl4-mesh create job --from=cronjob/pqc-key-rotation pqc-key-rotation-manual-$(date +%s)
   ```
2. Confirm new ML-KEM and ML-DSA fingerprints are active.
3. Verify the previous generation remains accepted only within the 7-day overlap window.
4. If backup recovery is required, unseal NTRU backup material under dual control and record approvers in the incident timeline.

### 30 to 60 minutes

1. Validate tenant-to-tenant denial with:
   ```bash
   kubectl -n <tenant-namespace> exec <pod> -- nc -vz <other-tenant-service> 7000
   ```
2. Export updated audit evidence and attach it to the incident ticket.
3. Confirm PagerDuty annotations link to the relevant Grafana dashboards and postmortem document.

## SEV-1: Audit log tampering

1. Compare `entry_hash` and `previous_hash` continuity for the affected day.
2. Restore the corresponding WORM-backed copy from the audit archive.
3. Preserve the altered node filesystem snapshot for forensic review.
4. Rotate all service credentials that had write access to the local audit directory.

## SEV-2: Scheduled rotation failure

1. Inspect the `pqc-key-rotation` CronJob and last job logs.
2. Verify SealedSecrets controller health and the target namespace RBAC.
3. Re-run the job manually and confirm secret timestamps updated.
4. Open a follow-up task if the overlap window would expire before the next successful run.

## Tenant isolation validation checklist

- `kubectl get networkpolicy,ciliumnetworkpolicy -A | grep x0tta`
- `kubectl auth can-i get secrets --as=system:serviceaccount:<tenant>:mesh-node-<tenant> -n <other-tenant-key-namespace>`
- Confirm every tenant has a dedicated application namespace and dedicated PQC key namespace
- Confirm no tenant service account has cluster-wide `get/list/watch` on secrets
- Render the enterprise chart with [render-in-docker.sh](/mnt/projects/charts/multi-tenant/render-in-docker.sh) before promoting values changes

## Audit evidence package

Attach all of the following to the incident:

- PagerDuty incident export
- Relevant Grafana dashboard snapshots
- Audit JSONL extracts and chain verification results
- `kubectl describe` output for the impacted namespaces, NetworkPolicies, CiliumNetworkPolicies, and SealedSecrets
- Post-rotation fingerprint manifest

## Quarterly review tasks

- Rehearse the key-compromise scenario end to end
- Verify WORM retention is still set to 365 days
- Validate all PagerDuty runbook URLs and escalation policies
- Reconcile tenant namespace inventory against [values-enterprise.yaml](/mnt/projects/charts/multi-tenant/values-enterprise.yaml)
- Re-run [run-local-sbom-check.sh](/mnt/projects/security/sbom/run-local-sbom-check.sh), [verify-cosign-rekor.sh](/mnt/projects/security/sbom/verify-cosign-rekor.sh), and [verify-local.sh](/mnt/projects/ebpf/prod/verify-local.sh) and update [evidence-matrix.md](/mnt/projects/compliance/soc2/evidence-matrix.md)
