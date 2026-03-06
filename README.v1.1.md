# x0tta6bl4 MaaS v1.1 - POC Validation Guide

## Overview
v1.1 introduces Federated Learning and Edge 5G capabilities. This POC is designed for **validation of logic and control loops** rather than physical performance benchmarking.

### Core Hardening (v1.1 Update)
- **Deterministic FedAvg**: Aggregation logic is validated against peer authorization, malformed updates, privacy-engine failures, and the successful aggregation path.
- **Privacy adapters**: `PrivacyEngine` now has explicit `SimulatedDPNoiseEngine`, `NoPrivacyEngine`, and `FutureRealDPEngine` paths. `SimulatedDPNoiseEngine` remains explicitly simulated, and `FutureRealDPEngine` is only a locally tested backend contract.
- **UPF Provider Interface**: The 5G path keeps `UPFProvider`, uses `SimulatedUPF` for local validation, and exposes `Open5GSUPFProvider` plus `Open5GSHTTPTransport` as locally tested transport scaffolds. Live Open5GS wiring is still NOT VERIFIED.
- **5G verification harness**: `scripts/verify-5g-path.sh` runs only the package-local `edge/5g` adapter tests and static eBPF source checks. It does not claim live Open5GS or live XDP enforcement.
- **Decision Handoff**: Backhaul routing remains deterministic and now separates simulated telemetry from future live SX1303 integration. The reader contract is locally testable, but hardware binding is still NOT VERIFIED.
- **QoS contract semantics**: `dao/qos/stake-multiplier.sol` uses X0T wallet balance as a stake proxy. Dedicated staking-contract integration is still NOT VERIFIED.
- **QoS test mirror**: `src/dao/contracts/contracts/QoSManager.sol` mirrors the root QoS contract for Hardhat, because Hardhat 2.x doesn't compile sources outside the project root.
- **QoS mirror guard**: `src/dao/contracts/scripts/check_qos_mirror_sync.sh` rejects drift between the root QoS contract and the Hardhat mirror before test results are treated as representative.
- **Metrics wiring**: Metric names are preserved for the POC, but this validation slice uses `internal/metrics/metricspoc.go` as an in-process recorder instead of claiming live Prometheus export.
- **eBPF control-plane path**: `RealEBPFQoSEnforcer` now has a dry-run programmer contract that is locally testable. Kernel/datapath attachment remains NOT VERIFIED.
- **Input/response guards**: adapter paths now reject empty UE IDs, negative simulated DP config, non-finite SX1303 samples, and invalid scaffold responses before those states can look like successful integration.

### Verification Matrix
See [VERIFICATION-MATRIX.md](./docs/v1.1/VERIFICATION-MATRIX.md) for a detailed breakdown of what is real vs. simulated.

### Running Validation
1. **Broader POC Test Sweep**:
   ```bash
   env GOCACHE=/mnt/projects/.tmp/go-build GOSUMDB=off \
     go test -v ./test ./ml/federated ./edge/5g ./backhaul/lora ./internal/metrics
   ```
   This sweep depends on the wider root module state outside the narrow 5G tranche.
2. **5G Path Verification**:
   ```bash
   bash scripts/verify-5g-path.sh
   ```
   This is the reproducible local verification path for the current 5G adapter contract.
3. **QoS Contract Tests**:
   ```bash
   cd src/dao/contracts
   npm ci
   npm run check:qos-mirror
   npm run test:qos
   ```
   This branch is currently verified with repo-local legacy peer resolution for the Hardhat toolbox stack.
4. **Observability**:
   Metrics labeled with `_simulated` provide feedback on the internal state of the POC loops.
