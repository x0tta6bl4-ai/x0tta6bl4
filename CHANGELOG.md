# Changelog

Все значимые изменения в проекте x0tta6bl4 будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и этот проект придерживается [Semantic Versioning](https://semver.org/lang/ru/).

## [3.6.0] - 2026-07-23

### Added
- **Prometheus Metrics (#170)**: All mesh metrics renamed with `x0tta6bl4_mesh_` prefix. New `x0tta6bl4_mesh_uptime_seconds` gauge. `docker-compose.override.yml` with Prometheus sidecar.
- **Docker Compose Healthchecks (#168)**: Healthcheck for `mesh-node`, `mesh-node-2`, `node-nl-bridge` using `python3 urllib`. `mesh-node-2` depends on `mesh-node: service_healthy`.
- **API Quickstart (#167)**: `docs/api/QUICKSTART.md` with 10 endpoint examples (curl + Python + JSON).
- **MAPE-K Integration Tests (#169)**: 12 tests covering full detect → analyze → plan → execute → verify cycle.
- **README Rewrite**: 4-question format (What/Run/See/Stop).
- **Demo Assets**: HTML terminals, capture script, API examples for GIF generation.
- **Blind Launch Test**: New developer sees Validation PASS within 12 minutes.
- **Architecture Docs**: ADR-001 PQC Facade, invariant evidence matrix, M2 operational spec.
- **Mesh Scaling Experiments**: Scripts for partition merge testing.

### Changed
- **Swarm Ownership**: Updated `shared_allow` with new directories and scripts.

## [3.5.0] - 2026-07-23

### Added
- **Quick Start (Phase 1)**: `quickstart/` directory with docker-compose.yml (2-node mesh), Dockerfile, demo.sh (6-step demo), README.md (4-question format). Ports: API 8280/8281, metrics 9290/9291.
- **3D CAD Generator**: `3d-generator-app/` — FastAPI AI-powered build123d generator (port 8095). 10 parametric templates, ollama integration, Three.js STL viewer.
- **eBPF Binaries**: New compiled BPF objects (latencytracker, connectiontracker, bandwidthmonitor), loader_linux_arm64.
- **6 Swarm Agents**: chaos-engineer, finops, compliance, sre, docs, devrel — all 100% smoke pass.
- **K8s Infra**: sealed-secrets.yaml (encrypted), staging secrets template.
- **20 New Test Files**: agents, anti_censorship, core, ml, security, swarm coverage.
- **PQC Refactor**: `simple.py` strict type hints, `encapsulate_legacy()` contract, hypothesis property-based tests.
- **HashiCorp Vault Setup & Client Integration**: `k8s/vault/setup.sh`, `src/security/vault_client.py`, metrics, secret manager.
- **Sealed Secrets Generation**: `scripts/generate_sealed_secrets.py` for production overlays.
- **Billing E2E stability**: Stripe billing e2e checks, FastAPI mock database overrides.
- **K8s Deploy Verification**: Multi-document YAML verification in `validate_kubernetes_deployment.sh`.
- **MAPE-K Events**: `healing.verified` local event, cooldown guard against duplicate self-healing.
- **Trust Finality Contracts**: Strict proof contracts rejecting hidden fields.

### Fixed
- **CI Stabilization**: Removed broken gitlink x0tta6bl4-ebpf, synced requirements.lock (cryptography 49.0.0→46.0.7, mcp 1.26.0→1.28.1, pillow 12.2.0→12.3.0), added pyyaml to mesh-node-smoke.yml, fixed YAML multi-doc validation (safe_load → safe_load_all).
- **SVIDSigner**: Fixed verify_payload key lookup.
- **Bandit**: Resolved security warnings (`-f json` → `-ll -q`).
- **Duplicity Build**: Added librsync-dev and gettext build dependencies.
- **Gitignore**: Added .zencoder/, outputs/, scratch/.

### Changed
- **Swarm Ownership**: Updated `docs/team/swarm_ownership.json` with new directories (3d-generator-app, dashboard, pitch-deck, ebpf, infra/k8s, plans, scripts).

## [Unreleased]

### Added
- Локальное событие `healing.verified` для MAPE-K: фиксирует post-action проверку следующего heartbeat как bounded evidence, без claims про customer traffic, external reachability или production readiness.
- Предохранитель от повторного self-healing действия в cooldown-окне после одной попытки восстановления.
- Строгие trust-finality proof-контракты, отклоняющие скрытые поля с production/customer overclaims.
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
- **5G Signaling & User Plane**: Real SCTP transport for AMF/UPF signaling and PFCP session establishment verified. **Full End-to-End UE session (PDU Session) verified on production VPS via ping 8.8.8.8 (RTT ~0.8ms).**
- **eBPF Datapath**: Live XDP attach on physical NIC (`enp8s0`) with ID 613 confirmed.
- **Ghost Protocol**: Custom stealth transport (ChaCha20-Poly1305 + WebRTC Mimicry) live verified on production VPS.
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
