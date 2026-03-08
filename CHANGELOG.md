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
