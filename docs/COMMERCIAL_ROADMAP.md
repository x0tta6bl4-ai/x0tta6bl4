# x0tta6bl4 Commercial & Technical Roadmap (Q1-Q2 2026)

## 1. Executive Summary
Проект x0tta6bl4 перешел от стадии R&D Mesh-ядра к коммерческой упаковке Enterprise-уровня. Технологический стек PQC (ML-KEM/ML-DSA) верифицирован, архитектура адаптирована под Multi-tenancy, и готов "Golden Path" для быстрого развертывания пилотов.

## 2. Product Matrix & Pricing (The Offer)

| Feature | **Pilot (POC)** | **Standard (Growth)** | **Enterprise (Shield)** |
|---------|-----------------|-----------------------|-------------------------|
| **Target** | Startups, Small Teams | SME, VPN Providers | Critical Infra, Gov, FinTech |
| **Nodes Limit** | Up to 5 nodes | Up to 50 nodes | Unlimited |
| **Cryptography** | Standard PQC-TLS | Standard PQC-TLS | Custom PQC Profiles + HSM |
| **Isolation** | Shared Cluster (ID-based) | Dedicated Namespace | Dedicated Cluster / On-Prem |
| **SLA/Support** | Best Effort | 99.9% / Business Hours | 99.99% / 24/7 Premium |
| **Pricing** | $500 / one-time (4 weeks) | $2,000 / month | Custom / Contract based |

## 3. Milestones (Next 90 Days)

### Phase 0: Packaging (Current - Day 30) - **DONE**
- [x] PQC Readiness Verification Script.
- [x] Enterprise B2B Landing Page.
- [x] Golden Path Deployment Script (`deploy_enterprise_demo.sh`).
- [x] Multi-tenancy Data & Log isolation.
- [x] **Next:** Tenant Quotas & Rate Limiting Enforcement.

### Phase 1: Validation (Day 30 - Day 60)
- [ ] Deploy 3 active Pilot instances for real B2B leads.
- [x] Integration with Billing (Stripe/Crypto Webhooks for Tenants).
- [x] Grafana "ROI Dashboard": Visual savings from Self-Healing MTTR.
- [x] Chaos-Mesh Demo script for Live Demos.

### Phase 2: Scale (Day 60 - Day 90)
- [x] Multi-region Mesh Federation (Inter-tenant connectivity).
- [x] Crisis Connectivity Kit (Offline-first provisioning).
- [x] DAO-based node staking for Enterprise partners.

## 4. Technical Gaps to Close
1. ~~**Quota Manager**: System to block node creation/traffic if tenant exceeds plan.~~ (DONE)
2. ~~**Attestation UI**: Simple dashboard for admins to see SBOM/PQC verification status of all nodes.~~ (DONE)
3. ~~**Automated Billing**: Logic to downgrade/revoke mesh instances on payment failure.~~ (DONE)
