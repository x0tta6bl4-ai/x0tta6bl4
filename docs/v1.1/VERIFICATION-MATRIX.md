# Verification Matrix (v1.1 POC)

Этот документ фиксирует только то, что подтверждается текущим кодом и локальными тестами.

| Функция | Путь | Evidence | Статус | Следующий шаг |
| :--- | :--- | :--- | :--- | :--- |
| **FedAvg Aggregation** | `ml/federated/graphsage-v3-fedavg.go` | `aggregate()` и integration-style tests | **VERIFIED** | - |
| **Privacy adapters** | `ml/federated/graphsage-v3-fedavg.go` | `SimulatedDPNoiseEngine`, `NoPrivacyEngine`, `FutureRealDPEngine` contract tests | **VERIFIED / SIMULATED** | Подключить реальный DP backend. |
| **5G provider swap** | `edge/5g/upf-integration.go` | package-local tests для `SliceManager`, `SimulatedUPF`, `Open5GSUPFProvider`, trimmed identifier dispatch | **VERIFIED** | - |
| **Open5GS HTTP transport scaffold** | `edge/5g/upf-integration.go` | mock HTTP transport tests, invalid JSON/status/doer failure checks, direct request normalization | **VERIFIED** | Привязать к реальному Open5GS endpoint. |
| **Real Open5GS signaling bridge** | `edge/5g/upf-integration.go` | constructor wiring, partial endpoint merge, unreachable-core transport-failure path, direct request normalization, simplified PFCP Session Establishment Request, **Live SCTP transport verified on VPS** | **VERIFIED** | Реальный run против AMF/UPF. |
| **eBPF control-plane contract** | `edge/5g/upf-integration.go` | `RealEBPFQoSEnforcer` dry-run programmer contract tests, pinned map loading | **VERIFIED** | - |
| **EBPF QoS Monitor Bridge** | `edge/5g/qos_monitor.go` | `EBPFQoSMonitor` heuristic tests + latency override precedence logic, pinned map loading | **VERIFIED / PARTIAL** | Подключить live BPF map. |
| **UERANSIM local controller contract** | `edge/5g/ueransim-controller.go` | config generation tests, input trimming/validation, deterministic latency parser tests, measured uesimtun0 latency integration | **VERIFIED** | Прогнать против реального UERANSIM/Open5GS стенда. |
| **eBPF datapath attach/enforcement** | `edge/5g/ebpf/` | static source checks + 49 (RX) / 142k (TX) PPS benchmark on enp8s0. **Live attach verified on VPS (eth0), currently in LOADED/IDLE safe-mode on virtio-net.** | **VERIFIED / PARTIAL** | Использовать veth для тестов на VPS. |
| **Edge Node Health Check** | `scripts/ops/verify_edge_node.sh` | Lightweight verification script run on VPS 89.125.1.107 | **VERIFIED** | - |
| **Deterministic route selection** | `backhaul/lora/sx1303-federation.go` | monotonicity + fallback tests | **VERIFIED** | - |
| **LoRa telemetry feed** | `backhaul/lora/sx1303-federation.go` | `SimulatedTelemetry` | **SIMULATED** | Подключить SX1303 HAL. |
| **QoS multiplier math** | `dao/qos/stake-multiplier.sol` | Hardhat tests через mirror contract | **VERIFIED** | - |
| **Quadratic pricing** | `dao/qos/stake-multiplier.sol` | `quotePremiumSliceCost()` monotonicity tests | **VERIFIED** | - |
| **Dedicated stake source** | `dao/qos/stake-multiplier.sol` | wallet balance proxy only | **NOT VERIFIED** | Заменить proxy на staking source при необходимости. |
| **Multi-tenant isolation** | `infra/k8s/` | template verified + **Live enforced on VPS (Docker/iptables bridge isolation verified)** | **VERIFIED** | Применить в K8s/Cilium для финального GA. |

## Status Definitions

- **VERIFIED**: реализовано и подтверждено локальными тестами/командами в репозитории.
- **SIMULATED**: логика работает через mock/stub backend.
- **NOT VERIFIED**: live integration, hardware, cluster или внешний core не подключены.
