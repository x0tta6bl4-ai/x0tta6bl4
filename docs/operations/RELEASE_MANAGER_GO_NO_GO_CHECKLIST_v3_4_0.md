# Release Manager Go/No-Go Checklist (v3.4.0)

**Дата:** `2026-03-05`  
**Scope:** MaaS API + mesh-operator release readiness

## 1) Preflight

- [ ] Версия согласована (`python3 scripts/validate_version_contract.py`).
- [ ] Ветка релиза синхронизирована с целевой (`main/develop`) без конфликтов.
- [ ] Нет открытых блокирующих инцидентов P0/P1.

## 2) Quality Gates

- [ ] `cd mesh-operator && go test ./...` — PASS.
- [ ] `bash scripts/ops/check_mesh_images_reproducibility.sh` — PASS.
- [ ] `bash scripts/ops/mesh_operator_kind_e2e.sh` — PASS.
- [ ] `bash scripts/ops/mesh_operator_webhook_admission_e2e.sh` — PASS.
- [ ] `bash scripts/ops/mesh_operator_helm_lifecycle_e2e.sh` — PASS.
- [ ] `bash scripts/ops/mesh_operator_canary_rollback_e2e.sh` — PASS.

## 3) Release Dry-Run Evidence

- [ ] `bash scripts/ops/mesh_operator_release_dry_run.sh` — PASS.
- [ ] Dry-run report JSON сохранён (`docs/release/mesh_operator_release_dry_run_<ts>.json`).
- [ ] Dry-run report MD сохранён (`docs/release/mesh_operator_release_dry_run_<ts>.md`).
- [ ] Контрольные точки `CP-01..CP-10` в статусе `PASS` или documented skip.

## 4) Security & Docs

- [ ] API docs обновлены под текущий контракт (`docs/api/API_REFERENCE.md`).
- [ ] Known limitations актуальны (`docs/KNOWN_LIMITATIONS_v3_4_0.md`).
- [ ] Архитектурная схема актуальна (`docs/01-architecture/ARCHITECTURE_DIAGRAMS.md`).
- [ ] Onboarding/quickstart актуальны (`docs/00-getting-started/quick-start.md`).

## 5) Rollback Readiness

- [ ] Canary rollback SLA подтверждён (`MAX_ROLLBACK_SECONDS` policy).
- [ ] Runbook rollback доступен для оператора:
  - `docs/operations/MESH_OPERATOR_RELEASE_DRY_RUN_RUNBOOK.md`
  - `docs/operations/db-migration-rollback-runbook.md`
- [ ] Команда знает команду быстрого отката Helm revision:
  - `helm rollback <release> <revision> --namespace <ns> --wait --timeout 300s`

## 6) Final Decision

- [ ] **GO**: все обязательные пункты закрыты.
- [ ] **NO-GO**: если любой блокирующий пункт не закрыт, релиз останавливается.
- [ ] Решение зафиксировано в release note / internal log с timestamp и ответственным.
