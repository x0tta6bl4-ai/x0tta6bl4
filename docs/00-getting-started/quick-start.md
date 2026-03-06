# Quick Start (v3.4.0)

Этот quickstart покрывает базовый dev-цикл: запуск API, smoke-проверки и mesh-operator e2e в `kind`.

## 1) Требования

- `python3` 3.12+
- `go` (для `mesh-operator`)
- `docker`, `kubectl`, `helm`, `kind` (для k8s/e2e)

## 2) Подготовка окружения

```bash
cd /mnt/projects
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Локальный запуск API

```bash
source .venv/bin/activate
uvicorn src.core.app:app --host 0.0.0.0 --port 8000 --reload
```

Проверка:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:8000/health/ready | python3 -m json.tool
```

## 4) Минимальные проверки перед PR

```bash
source .venv/bin/activate
python3 scripts/validate_version_contract.py
cd mesh-operator && go test ./...
cd ..
bash scripts/ops/check_mesh_images_reproducibility.sh
```

## 5) Mesh-operator: полный локальный e2e в kind

```bash
bash scripts/ops/mesh_operator_kind_e2e.sh
bash scripts/ops/mesh_operator_webhook_admission_e2e.sh
bash scripts/ops/mesh_operator_helm_lifecycle_e2e.sh
bash scripts/ops/mesh_operator_canary_rollback_e2e.sh
```

## 6) Release dry-run (контрольные точки)

Полный прогон:

```bash
bash scripts/ops/mesh_operator_release_dry_run.sh
```

Ускоренный локальный прогон (без тяжёлых e2e):

```bash
RUN_KIND_E2E=0 RUN_WEBHOOK_E2E=0 RUN_LIFECYCLE_E2E=0 RUN_CANARY_ROLLBACK_E2E=0 \
  bash scripts/ops/mesh_operator_release_dry_run.sh
```

## 7) Где смотреть артефакты

- Dry-run отчёты: `docs/release/`
- API спецификация: `docs/api/openapi.json`
- Архитектура (as-built): `docs/01-architecture/ARCHITECTURE_DIAGRAMS.md`
