# x0tta6bl4 MaaS v3.4.0 | GTM One-Pager
Date: 2026-03-05

## Positioning

x0tta6bl4 is a Mesh-as-a-Service platform for teams that need resilient, security-first network operations with explicit governance and measurable operational controls.

## Who It Is For

- Platform engineering teams running multi-site or hybrid workloads.
- Security teams rolling out Zero-Trust service identity and policy controls.
- Regulated pilots that need a documented path for PQC readiness and governance auditability.

## Problem

Teams are still forced to combine ad hoc VPN tooling, manual incident response, and fragmented policy governance. This increases MTTR, operational risk, and audit cost.

## Product Core (v3.4.0)

- Post-quantum-enabled control path: ML-KEM-768 + ML-DSA-65 support.
- Zero-Trust identity path with SPIFFE/SPIRE integration.
- MAPE-K recovery loops for autonomous response and controlled remediation.
- DAO governance CLI for proposal/vote/execute workflows on Base Sepolia (`chain_id=84532`).
- Kubernetes operator defaults with on-chain governance configuration fields.

## What Is Verified Now

- Version SSOT is `3.4.0`.
- PQC beacon server exposes `/mesh/pqc/pubkeys` and `/mesh/kem/session`.
- Governance CLI commands are implemented: `set-deployment`, `propose`, `vote`, `status`, `execute`, `list`, `info`.
- Helm values include DAO on-chain configuration (`meshDefaults.dao.governance.onChain`).
- ISO/IEC 27001:2025 documentation is a readiness baseline (not certification).

## Packaging For Pilots

1. Security pilot (4 weeks)
- Scope: 3-10 nodes, identity + PQC + governance workflow validation.
- Exit criteria: incident drill, audit trail capture, governance execution walkthrough.

2. Platform rollout (8-12 weeks)
- Scope: staged cluster rollout with observability and SLO tracking.
- Exit criteria: production runbook sign-off and operations handover.

3. Governance-enabled operations
- Scope: on-chain proposal/vote/execute flow with controlled release operations.
- Exit criteria: successful demo path `propose -> vote -> execute -> helm upgrade`.

## Compliance Messaging For External Use

- Allowed: "NIST FIPS 203/204 algorithm path implemented and tested with liboqs runtime."
- Allowed: "ISO/IEC 27001:2025 readiness baseline documented."
- Not allowed: "ISO certified."
- Not allowed: "Fully automated on-chain deployment execution is GA."

## Core CTA

- Book a pilot architecture review.
- Request the live governance demo.
- Evaluate Product Hunt launch artifacts and technical evidence matrix.

## Evidence Links

- `src/version.py`
- `src/core/app_minimal_with_pqc_beacons.py`
- `src/dao/governance_script.py`
- `charts/x0tta-mesh-operator/values.yaml`
- `docs/compliance/ISO_IEC_27001_2025_READINESS.md`
- `STATUS_REALITY.md`

