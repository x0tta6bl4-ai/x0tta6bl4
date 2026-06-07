# Pilot 0: Edge Mesh MaaS Runbook

## Status

Pilot 0 is a local/lab scenario for proving the basic MaaS operator path:

```text
temporary MaaS API -> mesh deploy -> Go agent register -> approve node ->
node-config -> heartbeat -> local heal -> evidence report
```

It is not a production launch. It does not prove customer traffic, external
reachability, external DPI bypass, settlement finality, production SLOs, or
production readiness.

## What To Run

Run from the repository root:

```bash
PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py \
  --require-ready \
  --output-dir docs/operations
```

Expected visible result:

```text
decision=PILOT0_EDGE_MESH_MAAS_READY
ready=true
json=docs/operations/pilot0_edge_mesh_maas_<timestamp>.json
markdown=docs/operations/pilot0_edge_mesh_maas_<timestamp>.md
```

The latest copies are also written to:

```text
docs/operations/pilot0_edge_mesh_maas_latest.json
docs/operations/pilot0_edge_mesh_maas_latest.md
```

## What This Proves

The report is allowed to claim only this local/lab evidence:

- temporary MaaS API started;
- mesh deploy endpoint returned join material;
- local Go agent binary built;
- agent node registered and was approved;
- agent fetched node-config;
- heartbeat was persisted in the temporary SQLite database;
- operator heal path ran after the real-agent heartbeat;
- restored-dataplane claim stayed bounded to the local probe path;
- raw target and runtime credentials stayed redacted.

## What This Must Not Claim

These claims must stay false in the JSON report:

```text
traffic_delivery_claim_allowed=false
customer_traffic_claim_allowed=false
external_reachability_claim_allowed=false
external_dpi_bypass_claim_allowed=false
settlement_finality_claim_allowed=false
production_slo_claim_allowed=false
production_readiness_claim_allowed=false
```

If any of these becomes true, treat the pilot report as blocked even if the
agent connected successfully.

## Lab Target Mode

By default the runner uses a temporary loopback TCP listener and redacts the
requested dataplane target. For a private lab target, set it locally and do not
paste it into chat:

```bash
export PILOT0_LAB_TARGET="10.0.0.5:443"
PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py \
  --require-ready \
  --use-supplied-dataplane-target \
  --dataplane-probe-target "$PILOT0_LAB_TARGET" \
  --output-dir docs/operations
```

Expected result is still a redacted report. The raw target must not appear in
the JSON or Markdown artifacts.

## Prerequisites

Check locally:

```bash
python3 --version
go version
python3 -m pip --version
```

The runner starts a temporary `uvicorn` MaaS API and builds `agent/` with Go.
It uses a temporary SQLite database under `.tmp/pilot0-edge-mesh-maas/`.

## Common Failures

### `go` is missing

Status: the Go agent cannot be built.

What to do: install Go locally, then rerun the command.

Expected result: the `go_agent_build` stage becomes `PASS`.

### MaaS API did not start

Status: the temporary local API did not answer `/health`.

What to do: inspect the JSON report field:

```text
failure.stage=local_maas_api_started
```

Expected result after fixing local Python dependencies: `local_maas_api_started`
is `PASS`.

### Heartbeat not observed

Status: the agent connected but did not persist heartbeat telemetry.

What to do: inspect the Markdown report and the temporary work directory shown
in `evidence.event_project_root`.

Expected result: `agent_heartbeat_persisted` is `PASS`.

### Report blocks production readiness

Status: this is expected.

What it means: Pilot 0 is local/lab evidence only. Production readiness needs
separate current evidence for live traffic, external reachability, SLOs,
settlement finality, and operational history.

## Fast Validation

After changing this runner or runbook, run:

```bash
python3 -m py_compile scripts/ops/run_pilot0_edge_mesh_maas.py
PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_run_pilot0_edge_mesh_maas.py -q --no-cov
```
