# Verification Matrix (v1.1 POC)

Этот документ фиксирует только то, что подтверждается текущим кодом и локальными тестами.

| Функция | Путь | Evidence | Статус | Следующий шаг |
| :--- | :--- | :--- | :--- | :--- |
| **FedAvg Aggregation** | `ml/federated/graphsage-v3-fedavg.go` | `aggregate()` и integration-style tests | **VERIFIED** | - |
| **Privacy adapters** | `ml/federated/graphsage-v3-fedavg.go` | `SimulatedDPNoiseEngine`, `NoPrivacyEngine`, `FutureRealDPEngine` contract tests | **VERIFIED / SIMULATED** | Подключить реальный DP backend. |
| **5G provider swap** | `edge/5g/upf-integration.go` | package-local tests для `SliceManager`, `SimulatedUPF`, `Open5GSUPFProvider` | **VERIFIED** | - |
| **Open5GS HTTP transport scaffold** | `edge/5g/upf-integration.go` | mock HTTP transport tests, invalid JSON/status/doer failure checks | **VERIFIED** | Привязать к реальному Open5GS endpoint. |
| **Real Open5GS signaling bridge** | `edge/5g/upf-integration.go` | constructor + unreachable-core test path | **NOT VERIFIED** | Реальный run против AMF/UPF. |
| **eBPF control-plane contract** | `edge/5g/upf-integration.go` | `RealEBPFQoSEnforcer` dry-run programmer contract tests | **VERIFIED** | - |
| **eBPF datapath attach/enforcement** | `edge/5g/ebpf/` | static source checks only | **NOT VERIFIED** | Live attach на реальном NIC. |
| **Deterministic route selection** | `backhaul/lora/sx1303-federation.go` | monotonicity + fallback tests | **VERIFIED** | - |
| **LoRa telemetry feed** | `backhaul/lora/sx1303-federation.go` | `SimulatedTelemetry` | **SIMULATED** | Подключить SX1303 HAL. |
| **QoS multiplier math** | `dao/qos/stake-multiplier.sol` | Hardhat tests через mirror contract | **VERIFIED** | - |
| **Quadratic pricing** | `dao/qos/stake-multiplier.sol` | `quotePremiumSliceCost()` monotonicity tests | **VERIFIED** | - |
| **Dedicated stake source** | `dao/qos/stake-multiplier.sol` | wallet balance proxy only | **NOT VERIFIED** | Заменить proxy на staking source при необходимости. |

## Status Definitions

- **VERIFIED**: реализовано и подтверждено локальными тестами/командами в репозитории.
- **SIMULATED**: логика работает через mock/stub backend.
- **NOT VERIFIED**: live integration, hardware, cluster или внешний core не подключены.
