# ArgoCD GitOps для x0tta6bl4

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        ArgoCD GitOps                            │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  AppProject │    │ApplicationSet│    │Notifications│        │
│  │  x0tta6bl4  │    │  x0tta6bl4  │    │   Config    │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                  │                   │               │
│         └──────────────────┼───────────────────┘               │
│                            │                                   │
│         ┌──────────────────┼──────────────────┐               │
│         │                  │                  │                │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐       │
│  │   Staging   │    │ Production  │    │    Redis    │       │
│  │ proxy-api   │    │  proxy-api  │    │  Sentinel   │       │
│  │  (auto)     │    │  (manual)   │    │   (auto)    │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Установка ArgoCD

```bash
# Создание namespace
kubectl create namespace argocd

# Установка ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Установка Argo Rollouts
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
```

## Применение конфигурации

```bash
# Применить все ArgoCD ресурсы
kubectl apply -k infra/argocd/

# Или по отдельности:
kubectl apply -f infra/argocd/appproject.yaml
kubectl apply -f infra/argocd/applications/
kubectl apply -f infra/argocd/notifications-cm.yaml
kubectl apply -f infra/argocd/argocd-rbac-cm.yaml
```

## Структура Applications

### proxy-api-staging
- **Branch**: `develop`
- **Auto-sync**: Enabled
- **Namespace**: `x0tta6bl4-staging`
- **Prune**: Yes (удаляет устаревшие ресурсы)
- **Self-heal**: Yes (восстанавливает drift)

### proxy-api-production
- **Branch**: `main`
- **Auto-sync**: Disabled (требуется ручной sync)
- **Namespace**: `x0tta6bl4-production`
- **Sync Windows**: Будни 10:00-18:00

## Sync Windows (Production)

| День | Время (UTC) | Разрешено |
|------|-------------|-----------|
| Пн-Пт | 10:00-18:00 | Да |
| Пт 22:00 - Пн 10:00 | - | Нет |
| Праздники | - | Manual only |

## RBAC Роли

| Роль | Права | Группы |
|------|-------|--------|
| `readonly` | Просмотр всех приложений | - |
| `developer` | Sync staging, просмотр prod | `developers` |
| `deployer` | Полный доступ | `sre-team` |
| `admin` | Администратор | `platform-team` |

## Уведомления

### Slack каналы
- `#deployments` - успешные деплои
- `#alerts` - ошибки синхронизации
- `#alerts-critical` - критические проблемы production

### Настройка Slack
```bash
# Создать секрет с токеном
kubectl create secret generic argocd-notifications-secret \
  -n argocd \
  --from-literal=slack-token=xoxb-YOUR-TOKEN
```

## GitOps Workflow

### Staging
```
develop branch → Auto-sync → x0tta6bl4-staging
```

### Production
```
main branch → PR Review → Manual Sync → x0tta6bl4-production
```

### Процесс деплоя в production

1. Создать PR из `develop` в `main`
2. Пройти code review
3. Merge PR
4. ArgoCD обнаружит изменения (OutOfSync)
5. Проверить diff в ArgoCD UI
6. Запустить sync вручную:
   ```bash
   argocd app sync proxy-api-production
   ```
7. Мониторить rollout:
   ```bash
   argocd app wait proxy-api-production --health
   ```

## Rollback

```bash
# Просмотр истории
argocd app history proxy-api-production

# Rollback к конкретной ревизии
argocd app rollback proxy-api-production <REVISION>

# Или через UI: Applications → proxy-api-production → History → Rollback
```

## Мониторинг

### ArgoCD Dashboard
```bash
# Порт-форвард
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Открыть https://localhost:8080
```

### Prometheus метрики
- `argocd_app_info` - информация о приложениях
- `argocd_app_sync_total` - количество синхронизаций
- `argocd_app_health_status` - статус здоровья

### Grafana Dashboard
ID: 14584 (ArgoCD Dashboard)

## Troubleshooting

### Application в OutOfSync
```bash
# Проверить diff
argocd app diff proxy-api-staging

# Принудительный sync
argocd app sync proxy-api-staging --force
```

### Sync Failed
```bash
# Посмотреть логи
argocd app logs proxy-api-staging

# Проверить events
kubectl get events -n x0tta6bl4-staging --sort-by='.lastTimestamp'
```

### Health Degraded
```bash
# Проверить pods
kubectl get pods -n x0tta6bl4-staging

# Посмотреть детали
argocd app get proxy-api-staging
```
