# DAO Proposal: x0tta6bl4-UTRECHT-PILOT-SCALE-GATE-2026-Q1

**Status:** Draft  
**Type:** Pilot Operations + Conditional Funding  
**Author:** Codex Implementer lane  
**Date:** 2026-03-04

## 1. Executive Summary
This proposal asks DAO to approve a controlled scale gate for the Utrecht 6G pilot after successful provisioning and baseline reliability validation.

## 2. Verified Baseline (as of 2026-03-04)
- Utrecht pilot was provisioned with:
  - `mesh_id=mesh-000d249803b2656f`
  - `nodes=50`
  - `billing_plan=enterprise`
  - `region=eu-west-utrecht`
  - `pqc_profile=robot`
  - `obfuscation=vless-reality`
- Staging preflight passed:
  - `make status` (core services healthy)
  - `make test` (health/metrics/db/redis/prometheus/grafana checks)
  - `make agent-cycle-dry` (`agent-1..4 rc=0`)
- Reliability drill passed:
  - `scripts/ops/run_reliability_drill.sh`
  - `timestamp_utc=20260304T173403Z`
  - `RESULT: SUCCESS`
- ISO readiness evidence snapshot exists:
  - `docs/compliance/EVIDENCE_SNAPSHOT_20260304T170224Z.md`
  - archive SHA256: `fd1073472046788e430758ba1b9d644eab9bbcbce0155a987fd27fc3bf380d93`

## 3. Proposal Scope
Approve a 7-14 day pilot observation window before scaling above 50 nodes.

Mandatory gates to move to 100+ nodes:
1. No unresolved P1 incidents during the observation window.
2. Daily reliability drill status recorded (success/failure + timestamp).
3. Dashboard evidence collected for uptime, latency, and recovery behavior.
4. Internal ISO readiness pack updated with new pilot artifacts.

## 4. Treasury Policy
This proposal requests **no immediate treasury disbursement**.

If all gates pass, a follow-up funding proposal will request budget for scale-up execution (100+ nodes) with explicit cost breakdown.

## 5. Risks and Mitigations
- Risk: Silent regression under real traffic.
  - Mitigation: Daily drill + dashboard review + incident runbook enforcement.
- Risk: Compliance overstatement.
  - Mitigation: Keep ISO status as internal readiness until audit prerequisites are complete.
- Risk: Kubernetes rollout delay due missing cluster context.
  - Mitigation: Continue pilot operations on current provisioning path; apply K8s manifest only on validated production context.

## 6. Voting Options
- **YES:** Approve the 7-14 day scale gate and evidence collection plan.
- **NO:** Keep pilot static at 50 nodes with no governance gate program.
- **ABSTAIN:** No preference.

## 7. Attachments
- `docs/operations/UTRECHT_6G_PILOT_RUNBOOK.md`
- `docs/compliance/EVIDENCE_SNAPSHOT_20260304T170224Z.md`
- `/tmp/x0tta6bl4-reliability-drill-20260304T173403Z.log`

---
*Prepared for DAO review on 2026-03-04.*
