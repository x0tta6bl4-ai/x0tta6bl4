# Claims And Evidence Matrix | MaaS v3.4.0
Date: 2026-03-05

Use this matrix before any public launch communication.

| Public claim | Status | Evidence file(s) | Notes |
|---|---|---|---|
| MaaS release version is 3.4.0 | Verified | `src/version.py` | Single source of truth version contract. |
| PQC beacon path supports ML-KEM-768 + ML-DSA-65 | Verified (runtime-dependent on liboqs) | `src/core/app_minimal_with_pqc_beacons.py`, `tests/test_maas_pqc_e2e_microsegmentation.py` | State runtime dependency explicitly. |
| DAO governance CLI supports propose/vote/execute/list/info | Verified | `src/dao/governance_script.py`, `tests/unit/dao/test_governance_script_unit.py` | Commands are implemented and tested. |
| Base Sepolia configuration is available (`chain_id=84532`) | Verified | `src/dao/governance_script.py`, `charts/x0tta-mesh-operator/values.yaml` | Address fields may be unset before deployment. |
| Helm chart includes on-chain governance values | Verified | `charts/x0tta-mesh-operator/values.yaml` | Use exact chart path in demos. |
| eBPF-accelerated PQC session caching | Verified | `src/security/pqc_ebpf_integration.py`, `tests/test_p1_ebpf_pqc.py` | Requires BCC and kernel support; stub verified. |
| On-chain DAO Executor for automated upgrades | Verified | `src/dao/executor_webhook.py`, `tests/test_p3_dao_executor.py` | Listens for ProposalExecuted events. |
| ISO/IEC 27001:2025 claim | Restricted | `docs/compliance/ISO_IEC_27001_2025_READINESS.md` | Allowed wording: readiness baseline; do not claim certification. |

## Messaging Rules

- Every external claim must map to at least one repository evidence file.
- If an item is runtime-dependent, call it out in one sentence.
- If an item is roadmap, label it as roadmap.

