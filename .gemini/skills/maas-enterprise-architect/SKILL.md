---
name: maas-enterprise-architect
description: Architectural guidelines and standards for x0tta6bl4 MaaS (Mesh-as-a-Service) Enterprise layer. Use when developing auth, billing, governance, or supply chain security for IoT/Robotics mesh networks.
---

# MaaS Enterprise Architect

This skill guides the development of the high-level service layer for x0tta6bl4, focusing on commercial readiness and corporate security.

## Core Architectural Pillars

### 1. Unified Identity & Auth (OIDC + RBAC)
- **Pattern**: External OIDC providers (Google, GitHub, Okta) map to internal `User` models.
- **Roles**:
  - `admin`: Full system control, audit log access, policy creation.
  - `operator`: Node approval, revocation, basic monitoring.
  - `user`: Mesh deployment, marketplace participation.
- **Implementation**: See `src/api/maas_auth.py`.

### 2. Transactional Integrity (Signed Playbooks)
- **Standard**: Every control-plane command sent to a headless agent MUST be signed.
- **Algorithm**: NIST-standard Post-Quantum ML-DSA-65 (fallback: HMAC-SHA256).
- **Flow**: `Create Playbook` (Control Plane) -> `Sign` -> `Poll/Push` -> `Verify` (Agent) -> `Ack`.

### 3. Sharing Economy (Node Marketplace)
- **Logic**: Peer-to-peer infrastructure renting.
- **Escrow**: Payment held until node successfully joins and maintains target mesh health.
- **Pricing**: Node-hour based, governed by DAO voting power.

### 4. Supply Chain Transparency (SBOM & Attestations)
- **Registry**: Store CycloneDX SBOMs for every agent release.
- **Verification**: Agents check their own integrity against Sigstore attestations on boot.

## Development Workflows

### Adding a New Enterprise Endpoint
1. Define Pydantic models in `src/api/maas.py` or specialized module.
2. Apply `require_role("admin"|"operator")` dependency.
3. Record action in `Audit Log` using `record_audit_log` or `_audit`.
4. Register router in `src/core/app.py`.

### Security Checklists
- [ ] No plaintext secrets in logs.
- [ ] PQC-secured tokens for all inter-mesh joins.
- [ ] Rate limiting applied to all public endpoints via `ApiKeyManager`.
