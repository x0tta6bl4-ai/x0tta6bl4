# x0tta6bl4 MaaS Pivot TODO

## Goal
Переход от consumer VPN к `Mesh-as-a-Service` платформе для IoT/Robotics/Edge с zero-trust, PQC и self-healing по умолчанию.

## North Star
- Product: `Control Plane + Headless Data Plane Agent`
- KPI:
  - MTTR < 1 min (target < 10 sec for routing failover)
  - Node onboarding time < 2 min
  - Zero-trust policy enforcement coverage: 100% новых узлов

## Phase 1: Headless Agent (Month 1)
- [x] Выпустить installer: `curl -sL ... | bash` (`agent/scripts/install.sh`)
- [x] systemd unit для `x0tta6bl4-agent` (`agent/scripts/x0t-agent.service`)
- [x] ARM64/ARMv7/x86_64 release artifacts (`agent/bin/`)
- [x] Control Plane API: node registration in `pending_approval`
- [x] Control Plane API: explicit `approve node` with signed join token

## Phase 2: Control Plane Console MVP (Month 2)
- [x] UI: список узлов — вкладка NODES с unified list (approved/pending/revoked + фильтры)
- [x] UI: кнопка `Approve Node` — в `pending_approvals.html` и вкладке PENDING
- [x] UI: топология mesh (MVP graph) — D3.js force-directed в `index.html`
- [x] API: node revoke + re-enroll flow

## Phase 3: Enterprise Layer (Month 3)
- [x] Tags + ACL profiles (`robot -> server`, `deny east-west`)
- [x] Audit log export — `GET /{mesh_id}/audit-logs/export?format=csv|json`
- [x] SSO (OIDC) for admins — `GET /auth/oidc/config`, `POST /auth/oidc/exchange`
- [x] On-prem deployment profile — `deploy/on-prem/docker-compose.yml`

## Phase 4: Marketplace & Ecosystem (Month 4)
- [x] Node Marketplace API — Rent/List/Search (`/marketplace`)
- [x] Terraform Provider — Resource `x0t_mesh` (Go-based)
- [x] Advanced Analytics Dashboard — ROI & Performance UI
- [x] Global Edge Network — Ansible deployment for Anchor Nodes

## Phase 5: Final Launch & Scale (Month 5)
- [x] Automatic Invoicing — Usage-based billing UI/API
- [x] Hardware Enclave Support — TPM 2.0 / SGX attestation
- [x] Mobile SDK Core — C-API headers & Python Bridge
- [x] Public Node Program — Enrollment flow & Governance rewards

## Project Status: v3.4.0-PRODUCTION-READY
- Tech: 95% (Scalable, Secured, Distributed)
- Commercial: 85% (Invoicing, Marketplace, Plans ready)
- **Goal Achieved: Ready for $10K MRR target.**

## Commercial Readiness
- [x] Plan catalog endpoint (`starter/pro/enterprise`)
- [x] Plan escalation guardrail (no higher-tier deploy than account plan)
- [x] Usage metering per mesh/node-hour (`GET /billing/usage`, `GET /billing/usage/{mesh_id}`)
- [x] Billing webhooks (upgrade/downgrade automation)

## Security Track (Cross-cutting)
- [x] Join token expiration and rotation policy (`POST /{mesh_id}/tokens/rotate`, TTL 1h–30d)
- [x] Signed control-plane playbooks for agent actions — PQC (ML-DSA-65) signatures
- [x] SBOM + Sigstore attestations for agent binaries — `GET /supply-chain/sbom/{v}`
- [x] Post-quantum profile defaults per segment — mapped to device_class

## Immediate Next 7 Days
- [x] Add `/nodes/revoke` + `/nodes/{id}/reissue-token`
- [x] Add MAPE-K event stream for node health to Control Plane
- [x] Add e2e test: register -> approve -> status -> revoke
- [x] Add first dashboard view for pending approvals
