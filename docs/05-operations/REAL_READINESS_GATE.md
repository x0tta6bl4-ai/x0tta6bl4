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
- The local dataplane EventBus collector can write proof-gate-compatible
  restored-dataplane evidence only after explicit local probe and write flags;
  it rejects non-local targets, hashes target metadata, and keeps
  traffic/customer/DPI/settlement/production claims false.
- Billing, MaaS billing, reward, marketplace, EventBus trace, and Mesh VPN
  relay surfaces keep settlement/dataplane/traffic/production claims behind
  explicit claim gates.
- Cross-plane proof gate exists for explicit production/dataplane/DPI/settlement
  claim checks and fails closed while current evidence is incomplete.
- API `_readiness_status` helpers under `src/api/*.py` carry
  `cross_plane_claim_gate` metadata, so local route/dependency readiness cannot
  silently become a production/dataplane/DPI/traffic/settlement claim.
- Authoritative and active public claim surfaces have no non-caveated
  high-risk production/DPI/traffic/settlement wording according to
  `scripts/claim_hygiene_scan.py`.
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
python3 -m pytest --no-cov tests/unit/scripts/test_check_real_readiness_unit.py -q
python3 -m pytest --no-cov tests/unit/scripts/test_collect_dataplane_delivery_eventbus_evidence.py -q
python3 -m pytest --no-cov tests/unit/scripts/test_run_cross_plane_proof_gate.py -q
python3 -m pytest --no-cov tests/unit/services/test_maas_auth_service_unit.py tests/api/test_maas_auth.py -q
npm --prefix x0tta6bl4-app run build
```
