# Packet: runbook_pilot_edge_mesh_lab

## Objective

Make the Pilot 1 Edge Mesh Lab handoff reviewable while keeping it explicitly
behind lab/operator approval and current evidence gates.

## Files

- `docs/runbooks/README.md`
- `docs/runbooks/PILOT1_EDGE_MESH_LAB.md`
- `config/chaos_agent.json`
- `scripts/ops/run_pilot0_edge_mesh_maas.py`
- `scripts/agents/chaos_engineer_agent.py`

## Work

- Added Pilot 1 to the runbook index.
- Fixed the runbook index link to the current incident response plan path:
  `docs/team/INCIDENT_RESPONSE_PLAN.md`.
- Verified the Pilot 1 runbook keeps secrets out of chat/tickets and blocks
  production, customer traffic, external DPI, settlement, and production-SLO
  claims.
- Verified the chaos-agent config parses and has the expected safety shape.
- Ran the local Pilot 0 preflight baseline and wrote evidence under
  `.tmp/validation-shards/pilot1-edge-mesh-lab/`.

## Boundaries

- This packet does not execute a real Pilot 1 lab node.
- It does not use production VPN listeners, shared customer infrastructure, or
  external targets.
- It does not prove customer traffic, external DPI bypass, settlement finality,
  production SLOs, or production readiness.
