# x0tta6bl4 MaaS v1.1 - 5G POC Setup
This guide covers UERANSIM integration with x0tta6bl4 MEC routing.

## Architecture
1. UERANSIM acts as simulated 5G UE/gNodeB.
2. Open5GS provides the Core Network (AMF/UPF).
3. x0tta6bl4 `upf-integration.go` hooks into UPF via eBPF XDP for slice-aware routing.

## Run Simulation
```bash
docker-compose -f docker-compose.5g-poc.yml up -d
```
Latency target: < 50ms handoff. Checked via Prometheus `upf_handoff_latency_ms`.