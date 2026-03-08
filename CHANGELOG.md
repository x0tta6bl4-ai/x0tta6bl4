# Changelog

Все значимые изменения в проекте x0tta6bl4 будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и этот проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Added
- Подготовка репозитория к публичной публикации
- Стандартизация структуры директорий
- GitHub шаблоны для Issues и Pull Requests
- CI/CD workflow для автоматического тестирования

## [3.2.1] - 2026-02-15

### Fixed
- **Critical**: Активация Production Lifespan (MAPE-K, FL, Swarm теперь запускаются автоматически).
- **Hotfix**: Интеграция Federated Learning в `launch_mvp.py`.
- **Hotfix**: Offline-fallback для Local LLM.

## [3.2.0] - 2026-01-25

### Added
- Federated Learning Orchestrator с Byzantine-отказоустойчивостью
- RAG Pipeline для интеллектуальной обработки документов
- Улучшенная интеграция с SPIFFE/SPIRE для Zero-Trust
- Chaos Engineering спецификации и тесты
- Поддержка eBPF для сетевой фильтрации

### Changed
- Оптимизация MAPE-K цикла самовосстановления
- Улучшена производительность mesh-сети Yggdrasil
- Обновлена документация API

### Fixed
- Исправлены race conditions в self-healing модуле
- Устранены утечки памяти в Federated Learning
- Исправлены ошибки в PQC реализации

### Security
- Обновлены зависимости с известными уязвимостями
- Улучшена валидация входных данных
- Добавлены security headers для API

## [3.0.0] - 2025-12-27

### Added
- Полная реализация Post-Quantum Cryptography (ML-KEM-768, ML-DSA-65)
- MAPE-K архитектура самовосстановления
- Mesh-сеть на базе Yggdrasil
- DAO Governance с quadratic voting
- Prometheus/Grafana мониторинг
- Полный набор тестов (87%+ coverage)

### Changed
- Рефакторинг ядра системы
- Улучшена модульность компонентов
- Оптимизация производительности

## [2.0.0] - 2025-11-15

### Added
- Базовая mesh-сеть
- VPN функциональность
- Telegram бот для продаж
- Система лицензирования

### Changed
- Переход на FastAPI
- Улучшена архитектура API

## [1.0.0] - 2025-10-01

### Added
- Первоначальный релиз
- Базовая инфраструктура
- Документация

---

## Типы изменений

- `Added` — новая функциональность
- `Changed` — изменения в существующей функциональности
- `Deprecated` — устаревшая функциональность
- `Removed` — удалённая функциональность
- `Fixed` — исправление ошибок
- `Security` — исправления безопасности

## [RC1] - 2026-03-08
### Added
- **5G Signaling Bridge**: Real SCTP transport for AMF/UPF signaling and PFCP session establishment (simplified) implemented.
- **eBPF Datapath**: Live XDP attach on physical NIC (`enp8s0`) with ID 613 confirmed.
- **Observability**: eBPF Prometheus Exporter with live telemetry and stub mode for CI validation.
- **Validation Bundle**: Empirical evidence collected for physical hardware performance.

### Fixed
- **Integrity**: Historical 8.8M PPS claim **PURGED** as unsubstantiated/simulated.
- **Baseline**: Adopted empirical baseline of **142k TX / 49 RX PPS** on physical NIC as current production-beta state.
- **Security**: Mitigated SEV-1 Python package vulnerabilities at repo level.

### Verified
- **10,008 Unit Tests passed** (MaaS Core, Security, 5G Adapters).
- **Physical NIC signal** (enp8s0): Baseline throughput recorded.

## [RC1.1] - 2026-03-08
### Added
- **eBPF Exporter Stub Mode**: `BPF_STUB_MODE=1` lets the exporter run without root or bpftool — enables CI metric validation.
- **Exporter Unit Tests**: 37 tests covering `compute_pps`, stub/live collection paths, env-config, and multi-cycle simulation (`tests/unit/monitoring/test_ebpf_exporter_unit.py`).
- **CI Smoke Gate** (`exporter-smoke` job in `ebpf-ci.yml`): starts exporter in stub mode, curls `/metrics`, asserts `x0tta6bl4_xdp_runs_total` and `x0tta6bl4_xdp_pps` are present with `iface="stub0"` label.
- **Prometheus scrape config** (`infra/prometheus.yml`): minimal config for `x0tta6bl4-ebpf` job on `localhost:9101`.

### Changed
- `scripts/ebpf_prometheus_exporter.py` refactored: extracted `collect_stats()`, `compute_pps()`, `_reset_stub_state()` as public API for testing; live bpftool calls isolated in `_live_get_run_cnt()` / `_live_get_iface()`.

## [RC1.2] - 2026-03-08
### Added
- **Mesh API Full Coverage**: `tests/unit/api/endpoints/test_mesh_unit.py` expanded 2 → 37 tests covering all 8 endpoints: `list_meshes`, `get_mesh_status`, `get_mesh_metrics`, `scale_mesh`, `terminate_mesh`, `get_mesh_audit`, `get_mesh_mapek`, plus `_build_mesh_status_response` helper.
- **MTTR Chaos Report**: `scripts/ops/mttr_chaos_report.py` — 10 synthetic chaos scenarios with SLO gate (MTTR ≤ 300s), JSON + Markdown output. CI-safe (no cluster required). 29 unit tests in `tests/unit/monitoring/test_mttr_chaos_report_unit.py`.
- **OpenMetrics Validator**: `scripts/ops/validate_metrics_endpoint.py` — stdlib-only endpoint validator for Prometheus text format, checks required metrics/labels/ranges. Integrated into `exporter-smoke` CI job.
- **RC1 Release Artifacts**: Evidence bundle, sign-off, status page and consistency gate (`scripts/ops/check_release_consistency.py`) committed to `docs/release/`.
- **Go Dataplane Bench CI**: 7 Go benchmarks (`ebpf/prod/bench_test.go`) + `benchstat` regression gate in `.github/workflows/go-dataplane-bench.yml`.

### Fixed
- `test_seed_deterministic` RNG ordering: load m2 after computing r1 so both runs start from the same seed state.

## [RC1.3] - 2026-03-08
### Added
- **MaaS Services Coverage**: `tests/unit/api/test_maas_services_mesh_provisioner_unit.py` — 46 tests for `MeshProvisioner` (provision/scale/terminate/approve_node/revoke_node), `UsageMeteringService` (request/bandwidth/storage/limits), and `_SharedStateStore` (disabled/enabled/error-suppression paths).
- **Pydantic Models Coverage**: `tests/unit/api/test_maas_models_unit.py` — 60 tests for all 13 MaaS request models validating required fields, regex patterns, min/max bounds, and defaults.
- **Auth Endpoint Full Coverage**: `tests/unit/api/endpoints/test_auth_unit.py` expanded 8 → 23 tests; adds internal helpers (`_hash_password`, `_verify_password`, `_normalize_email`) and all authenticated endpoints (`GET /me`, `POST /api-key`, `POST /logout`, `DELETE /account`).
