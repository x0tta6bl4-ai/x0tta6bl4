# Real-Readiness Gate

This gate is the current fail-closed entrypoint for checking whether the repo is
close to a reproducible x0tta6bl4 runtime. It is stricter than old score-based
readiness scripts: missing evidence blocks readiness.

## Command

```bash
python3 scripts/ops/check_real_readiness.py --write-json --write-md --json
```

Compatibility wrapper:

```bash
bash scripts/production-readiness-check.sh --write-json --write-md
```

## What It Proves

- App UI/server contract is pinned to port `8081`.
- Core API proxy target is explicit via `CORE_API_HOST` and `CORE_API_PORT`.
- App secrets are environment-only and `.env.example` secret placeholders are empty.
- API-key auth uses `api_key_hash`, not plaintext DB lookup.
- Alembic exposes one migration head.
- ORM/DB schema guard has parity and Alembic-head checks wired.
- Ghost VPN deployment uses `GHOST_VPN_AUTH_KEY`, not `GHOST_AUTH_KEY`.
- Ghost Pulse proof gate requires current runtime attach, not only historical evidence.
- MeshActionEnforcer and MaaS `heal_node` keep restored-dataplane claims behind
  bounded post-action dataplane probe evidence.
- MaaS API `heartbeat -> heal` has a runtime verifier that registers a redacted
  dataplane probe target, passes it into the heal manager, and keeps
  traffic/customer/external/SLO/production claims false.
- MaaS autonomous mesh runtime smoke is readiness-gated: it exercises local
  auth, mesh deploy, agent-style node enrollment, owner approval, heartbeat,
  heal, and service-trace claim classification in one in-process flow while
  keeping external infrastructure, customer traffic, SLO, and production claims
  false.
- Real Go-agent control-loop smoke builds the agent, runs it against a
  temporary MaaS API, observes node-config fetch and heartbeat, then forces the
  local node `offline` and requires operator heal to restore it to `healthy`
  through a temporary local TCP dataplane endpoint. Its restored-dataplane claim
  is allowed only for that bounded local proof; customer traffic, external
  reachability, SLO, and production readiness claims remain false.
- The local dataplane EventBus collector can write proof-gate-compatible
  restored-dataplane evidence only after explicit local probe and write flags;
  it rejects non-local targets, hashes target metadata, and keeps
  traffic/customer/DPI/settlement/production claims false.
- The dataplane operator-flow verifier ties the read-only handoff, opt-in
  collector, and proof-gate EventBus recognition path together in an isolated
  loopback smoke; it still does not prove real operator-run evidence, customer
  traffic, external reachability, SLO, or production readiness.
- The dataplane operator evidence runner gives an authorized operator one
  local command for private/link-local targets: without `--allow-operator-probe`
  it is read-only, and with the flag it writes redacted EventBus and proof-gate
  artifacts while keeping customer/traffic/production claims blocked.
- The private-target operator-run verifier has a readiness-gated blocked
  preflight: without `--allow-private-target-probe` it must stop before opening
  a socket or retaining operator-run evidence while redacting the target.
- The measured-attestation verifier handoff gives an authorized operator a
  read-only preflight for local report/quote/signature/provider/verifier inputs
  and prints smoke, validator, and proof-gate commands without exposing raw
  paths, verifier command, operator ID, authorization scope, or policy context.
- `TEEValidator` and the measured-attestation smoke support provider-aware
  SGX/SEV/Nitro local verifier commands. Missing commands, unsupported
  providers, mock providers, and overpromoted production-trust claims fail
  closed.
- Cross-plane proof-gate output includes the redacted measured-attestation
  handoff diagnostic when the verifier-smoke artifact is missing, so the local
  blocker names missing input classes without making the trust claim true.
- Billing, MaaS billing, modular `/billing/pay` responses, modular billing
  webhook lifecycle events, reward, marketplace, EventBus trace, and Mesh VPN
  relay surfaces keep settlement, paid-customer serviceability, node
  provisioning, dataplane, traffic, and production claims behind explicit claim
  gates.
- Cross-plane proof gate exists for explicit production/dataplane/DPI/settlement
  claim checks and fails closed while current evidence is incomplete.
- API `_readiness_status` helpers under `src/api/*.py` carry
  `cross_plane_claim_gate` metadata, so local route/dependency readiness cannot
  silently become a production/dataplane/DPI/traffic/settlement claim.
- Authoritative and active public claim surfaces have no non-caveated
  high-risk production/DPI/traffic/settlement wording according to
  `scripts/claim_hygiene_scan.py`.
- SafeActuator source adoption is parse-error-free and complete for current
  inventory: known high-risk control files are metadata-aware (`20/20`) and
  generic `SafeActuatorResult` result-call coverage is complete in source
  (`63/63`). The local runtime retention smoke confirms representative SPIRE,
  TokenBridge, DAO executor release-script, DAO proposal Helm upgrade, DAO
  governance dispatch, GovernanceContract chain-write, Ghost L3, eBPF, MaaS
  governance, PQC rotator, MPTCP, MeshActionEnforcer, self-healing MAPE-K,
  PBFT, Swarm MAPE-K, canary deployment, and multi-cloud deployment EventBus
  control events plus ops canary rollout, production monitor, auto-rollback, and production_deploy.py result metadata
  retain typed, redacted, fail-closed metadata (`18 EventBus + 4 ops
  result-metadata` local cases) without promoting live trust, dataplane, customer, settlement,
  consensus-finality, governance-finality, traffic shifting, throughput, SLO,
  or production claims.
- `production_deploy.py` also has a retained blocked-preflight evidence runner:
  it proves the local deploy path refuses live subprocess/kubectl execution
  without explicit authorization while preserving redacted SafeActuator
  metadata. It does not prove live deployment, traffic shifting, customer
  traffic, SLO, or production readiness.
- Economy/dataplane separation has a local smoke verifier: external settlement
  handoff, reward EventBus, marketplace EventBus, modular billing payment
  intent, modular billing webhook lifecycle, and service-trace economy summaries
  may record local/pending economy state, but must not promote dataplane
  delivery, customer traffic, revenue recognition, SLO, or production
  readiness.
- Swarm coordination is gated: executable `.githooks` hooks, ownership-map
  coverage, pre-commit staged-file lease enforcement, and post-commit lease
  release must satisfy `scripts/agents/check_coordination_contract.sh`.
- Current cross-plane evidence context exists in
  `docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json` and
  `docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md`.
- Current cross-plane evidence has no blocking gaps or next actions before this
  gate may return `REAL_READINESS_READY`.
- Docker Compose app and Ghost VPN configs render with required environment values.
- The release worktree is clean.

## Expected Current Result

During active development this command may return `REAL_READINESS_BLOCKED`
because the worktree can be dirty, command checks can fail, or the current
cross-plane evidence map can list blocking gaps. The former
`external-dpi-proof-missing` blocker is clear only when the redacted
`dpi_lab` candidate validates, the latest imported `dpi_lab` artifact validates,
and the proof gate allows only the bounded DPI-bypass subclaim while keeping
production, customer-traffic, settlement, anonymity, provider-health, and
durable-policy claims false.

## Follow-Up Evidence Before Claiming Ready

Run these after the gate is green or when investigating a specific blocker:

```bash
python3 -m alembic heads
python3 scripts/ops/run_cross_plane_proof_gate.py --json
python3 scripts/ops/run_cross_plane_proof_gate.py --output-json .tmp/validation-shards/cross-plane-proof-gate-current.json
python3 scripts/ops/verify_cross_plane_proof_gate_retention.py --require-valid
python3 scripts/ops/run_measured_attestation_verifier_handoff.py --require-ready --json
python3 scripts/ops/verify_maas_autonomous_mesh_runtime_smoke.py --dataplane-probe-target 10.123.45.67
python3 scripts/ops/verify_safe_actuator_metadata_adoption.py --require-high-risk-covered --require-full-coverage --json
python3 scripts/ops/verify_safe_actuator_runtime_metadata_retention.py --require-retained --json
python3 scripts/ops/run_production_deploy_blocked_preflight_evidence.py --require-retained --json
python3 scripts/ops/verify_maas_heal_api_post_action_dataplane_probe.py --target 10.123.45.67 --require-ready --json
python3 scripts/ops/verify_maas_real_agent_control_loop.py --dataplane-probe-target 10.123.45.67 --timeout-seconds 90
python3 scripts/ops/verify_dataplane_delivery_operator_flow.py --require-verified --json
# Readiness safe preflight; must block without opening a private-target probe:
python3 scripts/ops/verify_dataplane_delivery_private_target_operator_run.py --target-host 10.0.0.5 --require-retained --json
# Authorized dataplane operator run only; set the target locally, not in chat:
X0T_DATAPLANE_PROBE_HOST=<private_or_loopback_host> X0T_DATAPLANE_PROBE_PORT=<port> python3 scripts/ops/run_dataplane_delivery_operator_evidence.py --allow-operator-probe --require-retained --json
# Authorized local harness; binds one host-owned private non-loopback target and retains redacted artifacts:
python3 scripts/ops/verify_dataplane_delivery_private_target_operator_run.py --allow-private-target-probe --require-retained --json
# Includes modular billing payment-intent and webhook lifecycle evidence; still not settlement/finality/revenue proof.
python3 scripts/ops/verify_economy_dataplane_separation.py --require-separated --json
bash scripts/agents/check_coordination_contract.sh
python3 -m pytest --no-cov tests/unit/scripts/test_check_real_readiness_unit.py -q
python3 -m pytest --no-cov tests/unit/scripts/test_collect_dataplane_delivery_eventbus_evidence.py -q
python3 -m pytest --no-cov tests/unit/scripts/test_verify_dataplane_delivery_operator_flow.py -q
python3 -m pytest --no-cov tests/unit/scripts/test_run_dataplane_delivery_operator_evidence.py -q
python3 -m pytest --no-cov tests/unit/scripts/test_run_cross_plane_proof_gate.py -q
python3 -m pytest --no-cov tests/unit/services/test_maas_auth_service_unit.py tests/api/test_maas_auth.py -q
npm --prefix x0tta6bl4-app run build
```
