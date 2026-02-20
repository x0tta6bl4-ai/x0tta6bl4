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
- [ ] Выпустить installer: `curl -sL ... | bash`
- [ ] systemd unit для `x0tta6bl4-agent`
- [ ] ARM64/ARMv7/x86_64 release artifacts
- [x] Control Plane API: node registration in `pending_approval`
- [x] Control Plane API: explicit `approve node` with signed join token

## Phase 2: Control Plane Console MVP (Month 2)
- [ ] UI: список узлов (online/offline/pending)
- [ ] UI: кнопка `Approve Node`
- [ ] UI: топология mesh (MVP graph)
- [x] API: node revoke + re-enroll flow

## Phase 3: Enterprise Layer (Month 3)
- [x] Tags + ACL profiles (`robot -> server`, `deny east-west`)
- [ ] Audit log export (`who changed what`)
- [ ] SSO (OIDC) for admins
- [ ] On-prem deployment profile

## Commercial Readiness
- [x] Plan catalog endpoint (`starter/pro/enterprise`)
- [x] Plan escalation guardrail (no higher-tier deploy than account plan)
- [ ] Usage metering per mesh/node-hour
- [ ] Billing webhooks (upgrade/downgrade automation)

## Security Track (Cross-cutting)
- [ ] Join token expiration and rotation policy
- [ ] Signed control-plane playbooks for agent actions
- [ ] SBOM + Sigstore attestations for agent binaries
- [ ] Post-quantum profile defaults per segment

## Immediate Next 7 Days
- [x] Add `/nodes/revoke` + `/nodes/{id}/reissue-token`
- [ ] Add MAPE-K event stream for node health to Control Plane
- [ ] Add e2e test: register -> approve -> status -> revoke
- [x] Add first dashboard view for pending approvals
