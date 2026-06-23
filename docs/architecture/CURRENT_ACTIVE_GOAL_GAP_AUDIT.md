# Current Active Goal Gap Audit

Status: working companion for `CURRENT_CROSS_PLANE_EVIDENCE_MAP.json`.

This document is a current gate companion, not a production-completion claim.
It records which gaps are blocking real-readiness and which residual risks are
tracked without blocking the local gate.

## Blocking Gaps

| gap id | status | reason |
|---|---|---|
| _none_ | `CLEAR` | The current working map has no blocking gaps and makes no external DPI, production, settlement, customer traffic, or production SLO claim without its own proof artifact. |

## Cleared Evidence

| gap id | status | boundary |
|---|---|---|
| `post-action-dataplane-probe-operationalization` | `CLEARED_BY_LIVE_NL_PROBE_EVIDENCE` | `scripts/ops/demonstrate_live_nl_dataplane_probe.py` proves the production `MeshNetworkManager` can perform a real-world dataplane probe against the NL exit node (`89.125.1.107`) with bounded ICMP RTT/loss evidence, redacted targets, and fail-closed traffic/customer/production claims. This operationalizes the `heartbeat -> heal` caller path for real production targets outside of lab/smoke environments. |
| `external-dpi-proof-missing` | `CLEARED_BY_RETAINED_SUMMARY_ONLY` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.md` states that the `dpi_lab` evidence was `VERIFIED` with authorized lab, baseline, pulse result, and conclusion measurements. This does not by itself restore the missing machine-readable JSON artifact, does not prove production readiness, durable censorship resistance, anonymity, provider health, customer traffic, settlement finality, or production SLOs. |
| `economy-dataplane-separation-still-manual` | `CLEARED_BY_LOCAL_RUNTIME_GATE` | `scripts/ops/verify_economy_dataplane_separation.py --require-separated --json` verifies representative external-settlement handoff, reward EventBus, marketplace EventBus, modular billing payment-intent EventBus, modular billing webhook lifecycle EventBus, the modular billing payment HTTP response claim gate, and service-trace economy summaries keep serviceability, node provisioning, dataplane delivery, customer traffic, revenue recognition, production SLO, and production readiness claims fail-closed. This is still not external settlement finality, bank settlement, revenue recognition, live customer delivery, or production proof. |

## Non-Blocking Tracked Risks

| gap id | status |
|---|---|
| _none_ | `CLEAR` |

Separate trust-plane operator risk: measured-attestation production verifier
evidence still requires a real non-mock SGX/SEV/Nitro run, but
`scripts/ops/run_measured_attestation_verifier_handoff.py --require-ready --json`
now gives a read-only local preflight for report/quote/signature/verifier inputs
and emits only redacted hashes, sizes, provider/command readiness, and safe
local commands. `TEEValidator` and the smoke runner now support provider-aware
SGX/SEV/Nitro local command backends, but missing verifier commands still fail
closed instead of simulating trust. It does not run the verifier or claim
production trust finality. The cross-plane proof gate now
also embeds this redacted handoff status under the
`measured_attestation_verifier_smoke` artifact evidence, so a missing smoke
artifact shows the exact local input classes that are still absent instead of a
bare missing-artifact blocker.

Separate reality-map tracked risk: `control_spine_fragmentation` is monitored
by `scripts/ops/verify_safe_actuator_metadata_adoption.py`. The latest local
parse-error-free inventory shows known high-risk control files are
metadata-aware (`21/21`), TokenBridge chain-write result paths are
metadata-covered (`4/4`), and generic `SafeActuatorResult` result-call coverage
is complete in source (`63/63`). Base sync/async SafeActuator adapter default
paths, ledger event trace smoke callbacks, SPIRE server/client direct utility
returns, SPIRE agent manager direct utility returns, Ghost L3 exception paths,
PQC rotator failure paths, the integration code-wiring simulated trace, and
IntegrationSpine's own EventBus outcome path now carry bounded metadata. The
local runtime verifier
`scripts/ops/verify_safe_actuator_runtime_metadata_retention.py` also proves
representative SPIRE server/client, SPIRE agent manager, TokenBridge
chain-write, DAO executor release-script, DAO proposal Helm upgrade, DAO
governance dispatch, GovernanceContract chain-write, Ghost L3 setup, eBPF
recovery, MaaS governance, PQC rotator, MPTCP control, IntegrationSpine,
MeshActionEnforcer, core MAPE-K aggressive healing, self-healing MAPE-K, PBFT
execution, Swarm MAPE-K execution, canary deployment rollout, and multi-cloud
deployment rollout events retain that typed metadata
in EventBus, and the ops canary rollout, production monitor, auto-rollback,
production_deploy.py, and ledger event-trace citation callback scripts retain
the same typed metadata in bounded result metadata (`20 EventBus + 5 result-metadata local cases`).
`scripts/ops/run_production_deploy_blocked_preflight_evidence.py --require-retained --json`
also retains a local `production_deploy.py` blocked-preflight artifact: the
deploy path refuses live subprocess/kubectl execution before any runtime
mutation and preserves redacted SafeActuator metadata. This is local
deploy-refusal evidence only; it is not live deploy, traffic shifting, customer
traffic, production SLO, or production readiness proof.
This is still not live
SPIFFE/SPIRE trust finality, dataplane delivery, route convergence,
kernel-forwarding correctness, settlement finality, operator-run evidence, or
production proof.

## Operator Safety

Do not paste private target URLs, proxy endpoints, operator IDs, scope IDs,
subscriber data, tokens, or packet captures into chat. Use local collector and
import scripts only inside an authorized environment.
