# CI/CD Integration Guide

**Версия:** x0tta6bl4 v3.0  
**Дата:** $(date)

---

## Обзор

Расширенная интеграция canary deployment с популярными CI/CD системами. Автоматический rollback через API при обнаружении проблем.

---

## Поддерживаемые CI/CD системы

### 1. GitLab CI/CD

**Environment Variables:**
```bash
CI_SYSTEM=gitlab
CI_PROJECT_ID=123
CI_PIPELINE_ID=456
GITLAB_TOKEN=your_token
# или
CI_JOB_TOKEN=job_token
```

**Действия:**
1. Отменяет текущий pipeline
2. Запускает rollback pipeline с переменной `ROLLBACK=true`

---

### 2. GitHub Actions

**Environment Variables:**
```bash
CI_SYSTEM=github
GITHUB_REPOSITORY=user/repo
GITHUB_TOKEN=your_token
GITHUB_WORKFLOW_ID=rollback.yml  # опционально
```

**Действия:**
- Запускает rollback workflow через GitHub API

---

### 3. Jenkins

**Environment Variables:**
```bash
CI_SYSTEM=jenkins
JENKINS_URL=http://jenkins.example.com
JENKINS_USER=user
JENKINS_TOKEN=token
JENKINS_JOB_NAME=x0tta6bl4-rollback  # опционально
```

**Действия:**
- Запускает rollback job с параметром `ROLLBACK=true`

---

### 4. CircleCI

**Environment Variables:**
```bash
CI_SYSTEM=circleci
CIRCLE_TOKEN=your_token
CIRCLE_PROJECT_SLUG=gh/user/repo
```

**Действия:**
- Запускает rollback pipeline через CircleCI API

---

### 5. Azure DevOps

**Environment Variables:**
```bash
CI_SYSTEM=azure
AZURE_DEVOPS_ORG=org
AZURE_DEVOPS_PROJECT=project
AZURE_DEVOPS_PAT=pat
AZURE_PIPELINE_ID=123
```

**Действия:**
- Запускает rollback pipeline через Azure DevOps API

---

## Использование

### Автоматический Rollback

Rollback автоматически срабатывает при:
- Success rate < 95%
- Errors per minute > 10
- Health check failed

```python
from src.deployment.canary_deployment import CanaryDeployment

canary = CanaryDeployment()

# При проблемах автоматически:
# 1. Пытается Kubernetes rollback
# 2. Пытается Docker Compose rollback
# 3. Пытается CI/CD rollback (если настроено)
# 4. Scale down canary (fallback)
```

---

## Приоритет Rollback

1. **Kubernetes** (`kubectl rollout undo`)
2. **Docker Compose** (`docker compose rollback`)
3. **CI/CD System** (через API)
4. **Scale Down** (последний fallback)

---

## Тестирование

```bash
# Запустить тесты CI/CD интеграции
pytest tests/unit/deployment/test_canary_cicd_integration.py
```

---

## Настройка Rollback Pipeline

### GitLab CI/CD

```yaml
# .gitlab-ci.yml
rollback:
  only:
    variables:
      - $ROLLBACK == "true"
  script:
    - kubectl rollout undo deployment/x0tta6bl4
```

### GitHub Actions

```yaml
# .github/workflows/rollback.yml
name: Rollback
on:
  workflow_dispatch:
    inputs:
      rollback:
        type: boolean
        default: true
jobs:
  rollback:
    runs-on: ubuntu-latest
    steps:
      - name: Rollback
        run: kubectl rollout undo deployment/x0tta6bl4
```

---

## Мониторинг

Все rollback операции логируются:
- Успешный rollback: `✅ CI/CD rollback triggered`
- Ошибка: `❌ Rollback failed: {error}`

---

**Последнее обновление:** $(date)


