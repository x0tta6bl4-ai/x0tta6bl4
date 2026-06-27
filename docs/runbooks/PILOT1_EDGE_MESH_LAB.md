# Pilot 1: Edge Mesh Lab Runbook

## Status

Pilot 1 is the first real-lab step after Pilot 0. It keeps the same evidence
discipline, but moves from a fully local loop to one real edge node in an
isolated lab network:

```text
Pilot 0 ready -> one lab edge node -> MaaS API enrollment -> node approval ->
node-config -> heartbeat -> bounded heal check -> evidence packet
```

It is not a production launch. It does not prove customer traffic, external DPI
bypass, settlement finality, production SLOs, or production readiness.

## Goal

Prove that a real device can join the MaaS control plane as an edge node and
produce operator-visible evidence without making broader production claims.

The target visible result is a short evidence packet that answers:

- which lab node joined;
- which MaaS API accepted it;
- when it was approved;
- whether node-config was fetched;
- whether heartbeat telemetry was observed;
- whether a bounded heal action completed;
- which claims are still explicitly blocked.

## Inputs

Prepare these values locally. Do not paste secrets into chat or tickets.

```bash
export PILOT1_MAAS_API_BASE="http://127.0.0.1:8000"
export PILOT1_LAB_NODE_NAME="edge-lab-01"
export PILOT1_LAB_TARGET="10.0.0.5:443"
export PILOT1_OUTPUT_DIR="docs/operations/pilot1-edge-mesh-lab"
```

Use a private lab target owned by the pilot. Do not use production VPN listeners
or shared customer infrastructure as the lab target.

## Preflight

Run Pilot 0 first from the repository root:

```bash
PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py \
  --require-ready \
  --output-dir docs/operations
```

Expected visible result:

```text
decision=PILOT0_EDGE_MESH_MAAS_READY
ready=true
```

If Pilot 0 is blocked, stop here. Pilot 1 should not begin until the local MaaS
API and Go-agent control loop are green.

## Lab Target Smoke

Run the existing Pilot 0 runner in lab-target mode as a safe smoke test:

```bash
PYTHONPATH=. python3 scripts/ops/run_pilot0_edge_mesh_maas.py \
  --require-ready \
  --use-supplied-dataplane-target \
  --dataplane-probe-target "$PILOT1_LAB_TARGET" \
  --output-dir docs/operations
```

Expected result:

```text
decision=PILOT0_EDGE_MESH_MAAS_READY
ready=true
```

The raw lab target must stay redacted in the generated JSON and Markdown
artifacts.

## Real Node Enrollment

Install or start the headless agent on the lab edge node using the project
agent packaging for the device architecture.

Record these facts in the pilot notes:

```text
node_name=<lab node name>
device_class=<robot|iot|edge|server>
architecture=<amd64|arm64|armv7>
network=<isolated lab network name>
api_base=<redacted or private API base>
started_at=<UTC timestamp>
```

The node should enter `pending_approval`, then be approved by the MaaS control
plane, then fetch node-config and emit heartbeat telemetry.

## Evidence To Collect

Create the output directory:

```bash
mkdir -p "$PILOT1_OUTPUT_DIR"
```

Save only redacted evidence:

```text
$PILOT1_OUTPUT_DIR/node-registration.md
$PILOT1_OUTPUT_DIR/node-config.md
$PILOT1_OUTPUT_DIR/heartbeat.md
$PILOT1_OUTPUT_DIR/heal-check.md
$PILOT1_OUTPUT_DIR/claim-boundary.md
```

Each note should include:

- UTC timestamp;
- command or API endpoint used;
- visible result;
- redacted node identifier;
- pass/fail decision;
- short failure reason when blocked.

## Pass Gate

Pilot 1 is ready only if all required checks pass:

```text
pilot0_preflight_ready=true
lab_target_smoke_ready=true
real_lab_node_registered=true
real_lab_node_approved=true
node_config_seen=true
heartbeat_seen=true
bounded_heal_seen=true
raw_targets_redacted=true
runtime_credentials_redacted=true
```

If any required check is false, mark the pilot as blocked and keep the evidence
packet. A blocked packet is still useful because it shows where the next fix is.

## Claims Allowed

Pilot 1 may claim only this:

- one real lab edge node completed MaaS enrollment;
- the operator approved the node;
- the node fetched config from the control plane;
- heartbeat telemetry was observed;
- a bounded lab heal check completed;
- evidence was redacted before sharing.

## Claims Not Allowed

These claims must remain false unless separate current evidence exists:

```text
customer_traffic_claim_allowed=false
external_reachability_claim_allowed=false
external_dpi_bypass_claim_allowed=false
settlement_finality_claim_allowed=false
production_slo_claim_allowed=false
production_readiness_claim_allowed=false
```

## Rollback

If the lab node behaves unexpectedly:

1. Revoke the lab node in MaaS.
2. Stop only the lab agent process or lab device service.
3. Preserve logs and redacted evidence.
4. Do not stop or disable production VPN services as part of this pilot.

## Common Failures

### Node stays pending

Status: the agent registered, but no operator approval happened.

What to do: approve the node in the MaaS control plane and re-check node-config.

Expected result: the node leaves `pending_approval` and starts fetching config.

### Heartbeat is missing

Status: the node was approved but is not reporting health.

What to do: check agent logs on the lab node and verify it can reach the MaaS
API base URL.

Expected result: a fresh heartbeat appears in MaaS telemetry.

### Heal check is blocked

Status: the node is visible, but the bounded heal check did not complete.

What to do: keep the evidence packet and classify the failing stage before
retrying.

Expected result: the next run should show either `bounded_heal_seen=true` or a
clearer blocked reason.
