# Developer Onboarding (v3.4.0)

## Цель

Ввести разработчика в рабочий цикл репозитория за один день: setup -> код -> проверки -> PR.

## 1) Bootstrap

```bash
cd /mnt/projects
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Ключевые директории

- `src/core/` — app composition, middleware, reliability/security.
- `src/api/` — MaaS/VPN/Swarm/Edge/Event API.
- `src/database/` — ORM модели и DB wiring.
- `mesh-operator/` + `charts/x0tta-mesh-operator/` — k8s control-plane.
- `scripts/ops/` — e2e и release gates.
- `plans/MASTER_100_READINESS_TODOS_2026-02-26.md` — live roadmap.

## 3) Ежедневный baseline

```bash
source .venv/bin/activate
python3 scripts/validate_version_contract.py
cd mesh-operator && go test ./...
cd ..
```

## 4) Если изменения касаются operator/release

```bash
bash scripts/ops/check_mesh_images_reproducibility.sh
bash scripts/ops/mesh_operator_helm_lifecycle_e2e.sh
bash scripts/ops/mesh_operator_canary_rollback_e2e.sh
```

## 5) Проверка API-контрактов и ошибок

- OpenAPI: `docs/api/openapi.json`
- Runtime error envelope: `src/core/api_error_handlers.py`  
  формат: `status/detail/code/trace_id`

## 6) Перед PR

- Обновить документацию при user-facing изменениях.
- Добавить/обновить тесты.
- Пройти локальный smoke для затронутого слоя.
- Обновить roadmap progress log при закрытии пункта.

## 7) Полезные команды `make`

```bash
make mesh-operator-reproducibility
make mesh-operator-lifecycle-e2e
make mesh-operator-canary-rollback-e2e
make mesh-operator-release-dry-run
```
