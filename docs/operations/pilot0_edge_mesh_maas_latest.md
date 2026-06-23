# Pilot 0: Edge Mesh MaaS Report

- Decision: `PILOT0_EDGE_MESH_MAAS_READY`
- Ready: `true`
- Generated: `2026-06-07T18:26:50Z`
- Source verifier: `scripts/ops/verify_maas_real_agent_control_loop.py`
- Runbook: `docs/runbooks/PILOT0_EDGE_MESH_MAAS.md`

## Operator-visible result

| Check | Status |
|---|---|
| MaaS API started | PASS |
| Mesh deployed | PASS |
| Agent node registered | PASS |
| Agent node approved | PASS |
| Node config observed | PASS |
| Heartbeat observed | PASS |
| Heal observed | PASS |
| Production overclaim blocked | PASS |

## Claim boundary

Pilot 0 Edge Mesh MaaS is a local/lab operator scenario. It proves that a temporary MaaS API can start, a locally built Go agent can register, be approved, fetch node-config, send heartbeat telemetry, and exercise a bounded operator heal path with redacted evidence. It does not prove live customer traffic, external reachability, external DPI bypass, settlement finality, production SLOs, durable infrastructure convergence, or production readiness.

## Strong claims intentionally blocked

- `traffic_delivery_claim_allowed`
- `customer_traffic_claim_allowed`
- `external_reachability_claim_allowed`
- `external_dpi_bypass_claim_allowed`
- `settlement_finality_claim_allowed`
- `production_slo_claim_allowed`
- `production_readiness_claim_allowed`

## Local/lab claims allowed by this report

- Local MaaS API start: `True`
- Real Go agent connected: `True`
- Heartbeat persisted locally: `True`
- Bounded heal path observed: `True`

## Evidence

- Source decision: `MAAS_REAL_AGENT_CONTROL_LOOP_SMOKE_READY`
- Source duration ms: `63092.929`
- Event project root: `/mnt/projects/.tmp/pilot0-edge-mesh-maas/20260607T182650Z`
- JSON artifact: `docs/operations/pilot0_edge_mesh_maas_20260607T182650Z.json`
- Markdown artifact: `docs/operations/pilot0_edge_mesh_maas_20260607T182650Z.md`

## Reproduce

```bash
PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py --require-ready --output-dir docs/operations
```
