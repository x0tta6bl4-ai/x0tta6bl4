# Argo Rollouts Canary Deployment

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    Canary Deployment Flow                       │
│                                                                 │
│  ┌─────────────┐                      ┌─────────────┐          │
│  │   Stable    │◄──── 95% traffic ────│   Istio     │          │
│  │  (v1.0.0)   │                      │ VirtualSvc  │          │
│  └─────────────┘                      └──────┬──────┘          │
│                                              │                  │
│  ┌─────────────┐                             │                  │
│  │   Canary    │◄────  5% traffic ───────────┘                  │
│  │  (v1.1.0)   │                                               │
│  └──────┬──────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Analysis  │───►│  Prometheus │───►│  Pass/Fail  │        │
│  │  Template   │    │   Metrics   │    │  Decision   │        │
│  └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Стратегия Canary

| Шаг | Трафик | Длительность | Анализ |
|-----|--------|--------------|--------|
| 1 | 5% | 2 мин | - |
| 2 | 5% | - | Smoke tests |
| 3 | 10% | 5 мин | - |
| 4 | 10% | - | Error rate |
| 5 | 25% | 10 мин | - |
| 6 | 25% | - | Latency |
| 7 | 50% | 15 мин | - |
| 8 | 50% | - | Full analysis |
| 9 | 75% | 10 мин | - |
| 10 | 75% | - | Pre-promotion |
| 11 | 100% | - | Complete |

**Общее время rollout: ~45-60 минут**

## Установка

```bash
# Установить Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Установить kubectl plugin
brew install argoproj/tap/kubectl-argo-rollouts

# Применить конфигурацию
kubectl apply -k infra/argo-rollouts/
```

## Использование

### Запуск деплоя

```bash
# Обновить image в Rollout
kubectl argo rollouts set image proxy-api \
  proxy-api=x0tta6bl4/proxy-orchestrator:v1.1.0 \
  -n x0tta6bl4-production

# Или изменить манифест и применить
kubectl apply -f infra/argo-rollouts/proxy-api-rollout.yaml
```

### Мониторинг

```bash
# Статус rollout
kubectl argo rollouts get rollout proxy-api -n x0tta6bl4-production

# Watch mode
kubectl argo rollouts get rollout proxy-api -n x0tta6bl4-production --watch

# Dashboard
kubectl argo rollouts dashboard -n x0tta6bl4-production
```

### Ручное управление

```bash
# Promote canary (перейти к следующему шагу)
kubectl argo rollouts promote proxy-api -n x0tta6bl4-production

# Full promote (сразу 100%)
kubectl argo rollouts promote proxy-api --full -n x0tta6bl4-production

# Abort (откат)
kubectl argo rollouts abort proxy-api -n x0tta6bl4-production

# Retry после abort
kubectl argo rollouts retry rollout proxy-api -n x0tta6bl4-production
```

## Analysis Templates

### smoke-test
- Проверяет /health endpoint
- Проверяет /metrics endpoint
- Проверяет /api/v1/status

### error-rate-analysis
- Error rate < 5% (success)
- Error rate >= 10% (failure)
- Success rate > 95%

### latency-analysis
- P50 latency < 100ms
- P99 latency < 500ms
- Canary не медленнее stable > 20%

### full-analysis
- Error rate < 2%
- P99 latency < 500ms
- Pod restarts = 0
- Memory usage < 85%
- CPU usage < 80%

### pre-promotion-analysis
- Финальная проверка health
- Нет ошибок за последние 5 минут

## Тестирование Canary

### Header-based routing

```bash
# Запрос к canary (через header)
curl -H "x-canary: true" https://proxy-api.x0tta6bl4.io/api/v1/status

# Запрос к stable
curl https://proxy-api.x0tta6bl4.io/api/v1/status
```

### Проверка traffic split

```bash
# 100 запросов
for i in {1..100}; do
  curl -s https://proxy-api.x0tta6bl4.io/api/v1/version | jq -r '.version'
done | sort | uniq -c
```

## Rollback

### Автоматический

Происходит когда:
- AnalysisRun возвращает Failed
- Превышено количество failureLimit в metrics
- Pods не становятся Ready

### Ручной

```bash
# Abort текущего rollout
kubectl argo rollouts abort proxy-api -n x0tta6bl4-production

# Undo к предыдущей ревизии
kubectl argo rollouts undo proxy-api -n x0tta6bl4-production

# Undo к конкретной ревизии
kubectl argo rollouts undo proxy-api --to-revision=2 -n x0tta6bl4-production
```

## Метрики и Alerting

### Prometheus метрики

```promql
# Rollout статус
argo_rollouts_info{name="proxy-api", namespace="x0tta6bl4-production"}

# Canary weight
argo_rollouts_desired_replicas{name="proxy-api", namespace="x0tta6bl4-production"}

# Analysis результаты
argo_rollouts_analysis_run_phase{name=~"proxy-api.*"}
```

### Alerting rules

```yaml
- alert: RolloutStalled
  expr: |
    time() - argo_rollouts_analysis_run_last_timestamp{namespace="x0tta6bl4-production"} > 1800
  labels:
    severity: warning
  annotations:
    summary: "Rollout stalled for more than 30 minutes"

- alert: RolloutFailed
  expr: |
    argo_rollouts_info{phase="Degraded"} == 1
  labels:
    severity: critical
  annotations:
    summary: "Rollout failed and was rolled back"
```

## Troubleshooting

### Rollout застрял на Analysis

```bash
# Проверить AnalysisRun
kubectl get analysisrun -n x0tta6bl4-production

# Описать проблемный AnalysisRun
kubectl describe analysisrun <name> -n x0tta6bl4-production

# Проверить Jobs
kubectl get jobs -n x0tta6bl4-production -l rollouts-pod-template-hash
```

### Canary не получает трафик

```bash
# Проверить VirtualService
kubectl get vs proxy-api -n x0tta6bl4-production -o yaml

# Проверить weights
kubectl argo rollouts get rollout proxy-api -n x0tta6bl4-production

# Проверить Istio proxy
istioctl proxy-status
```

### Metrics не работают

```bash
# Проверить Prometheus
kubectl port-forward svc/prometheus -n monitoring 9090:9090

# Тестировать query
curl 'http://localhost:9090/api/v1/query?query=up{job="proxy-api"}'
```
