# Product Hunt Assets | x0tta6bl4 MaaS v3.4.0
Date: 2026-03-05  
Scope: Listing copy + maker narrative + comment replies + social snippets

## 1. Listing Copy

Primary tagline (<=60 chars):
Self-Healing Post-Quantum Mesh-as-a-Service

Tagline alternatives:
- Quantum-ready mesh operations for security teams
- Zero-Trust MaaS with autonomous recovery loops
- Operate resilient meshes with PQC and DAO governance

Primary description (<=260 chars):
Self-healing Mesh-as-a-Service with post-quantum cryptography, SPIFFE/SPIRE Zero-Trust identity, and on-chain governance tooling on Base Sepolia. Deploy with Helm, monitor with Prometheus, and recover incidents via MAPE-K automation.

Topics:
- Cybersecurity
- Developer Tools
- DevOps
- Open Source
- Web3

## 2. Verified Feature Bullets

- Post-quantum stack: ML-KEM-768 and ML-DSA-65 with `liboqs` runtime support.
- Zero-Trust identity: SPIFFE/SPIRE integration for workload identities.
- Governance operations: DAO CLI supports `propose`, `vote`, `status`, `execute`, `list`, and `info`.
- Kubernetes path: `x0tta-mesh-operator` chart includes `dao.governance.onChain` settings for Base Sepolia (`chainId=84532`).
- Autonomic recovery: MAPE-K loops included in production architecture.

## 3. Compliance Badge Set

Use these badges in PH comment, landing, and one-pager:

- `ML-KEM-768` | Status: verified in code path
- `ML-DSA-65` | Status: verified in code path
- `ISO/IEC 27001:2025 readiness` | Status: in progress (readiness baseline, not certification)
- `Base Sepolia DAO` | Status: governance CLI ready on `chain_id=84532`

Markdown snippet:

```md
![ML-KEM-768](https://img.shields.io/badge/ML--KEM--768-verified-success)
![ML-DSA-65](https://img.shields.io/badge/ML--DSA--65-verified-success)
![ISO 27001:2025](https://img.shields.io/badge/ISO%2FIEC%2027001%3A2025-readiness-yellow)
![Base Sepolia DAO](https://img.shields.io/badge/Base%20Sepolia-84532-blue)
```

## 4. Maker First Comment

Hi Product Hunt, I am the maker of x0tta6bl4.

We built this because most teams still operate critical access paths with manual VPN workflows and weak recovery automation. MaaS v3.4.0 is our production-focused release for teams that need resilient mesh operations, quantum-ready crypto primitives, and explicit governance workflows.

What is in this release:
- PQC beacon protocol with ML-KEM-768 and ML-DSA-65 support.
- DAO governance CLI on Base Sepolia for proposal/vote/execute operations.
- Helm defaults for on-chain governance fields in the mesh operator.
- MAPE-K-driven recovery logic integrated into the platform runtime.

Important transparency note:
- ISO/IEC 27001:2025 status is readiness baseline documentation, not a completed certification claim.
- DAO event-driven automatic Helm executor is a planned next step (P3); current demo uses governance execution plus controlled operator action.

I will be here today for technical questions on PQC, Zero-Trust identity, and rollout strategy.

## 5. Ready Replies For Product Hunt Comments

Q: Is this production-ready or still prototype?  
A: Core MaaS capabilities are in production path (`v3.4.0`). We still distinguish between ready features and planned workstreams, and we publish that boundary in `STATUS_REALITY.md`.

Q: Are you claiming ISO certification?  
A: No. Current claim is ISO/IEC 27001:2025 readiness baseline documentation. Certification is not claimed.

Q: Is governance fully on-chain and automated into deployments?  
A: Governance proposal/vote/execute is on-chain via CLI. Automated Helm execution from on-chain events is planned as the next phase.

Q: Which PQC standards do you implement?  
A: ML-KEM-768 (FIPS 203) and ML-DSA-65 (FIPS 204) with `liboqs` runtime support.

Q: Do I need Kubernetes?  
A: For enterprise rollout, yes. For local evaluation, API + governance CLI can be tested without full cluster installation.

## 6. Social Snippets

X/Twitter:

```text
We just launched x0tta6bl4 MaaS v3.4.0 on Product Hunt.
Self-healing mesh operations + PQC-ready crypto + Zero-Trust identity + DAO governance workflows.
Feedback from security/DevOps teams is very welcome.
[PH LINK]
```

LinkedIn:

```text
Today we launched x0tta6bl4 MaaS v3.4.0 on Product Hunt.

This release focuses on enterprise mesh operations:
- Post-quantum cryptography path (ML-KEM-768, ML-DSA-65)
- SPIFFE/SPIRE-based Zero-Trust identity
- DAO governance tooling on Base Sepolia
- MAPE-K self-healing architecture

We are explicitly separating verified capabilities from roadmap items, and we welcome technical feedback from platform and security teams.
[PH LINK]
```

## 7. Media Asset Checklist (PH Gallery)

- Screenshot 1: mesh health and peer topology status.
- Screenshot 2: PQC beacon/public key endpoint output.
- Screenshot 3: governance proposal creation from CLI.
- Screenshot 4: governance vote and execution status.
- Screenshot 5: Helm values `dao.governance.onChain` section.
- Video (60-90s): `propose -> vote -> execute -> controlled helm upgrade`.

## 8. Source Of Truth

- `src/version.py`
- `src/core/app_minimal_with_pqc_beacons.py`
- `src/dao/governance_script.py`
- `charts/x0tta-mesh-operator/values.yaml`
- `docs/compliance/ISO_IEC_27001_2025_READINESS.md`
- `STATUS_REALITY.md`
