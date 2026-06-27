# Руководство по развертыванию критических оптимизаций инфраструктуры x0tta6bl4

## Обзор

Этот документ описывает процесс развертывания критических оптимизаций для решения выявленных проблем производительности и надежности в многорегиональной инфраструктуре x0tta6bl4.

## Целевые проблемы для решения

### Фаза 1 (Текущая)
- **BATMAN-adv тайм-ауты:** 15-20% узлов >30с при пиковой нагрузке
- **SPIFFE/SPIRE единая точка отказа** вызывает каскадные сбои
- **HNSW индексы деградация** на 15% из-за задержек репликации
- **mTLS handshake задержки** 15-25мс на соединение
- **Cilium eBPF ложные срабатывания** 12% случаев

## Архитектура оптимизаций

```
┌─────────────────────────────────────────────────────────────────┐
│                    Многорегиональная инфраструктура              │
├─────────────────────────────────────────────────────────────────┤
│  🌎 US East    🌍 EU West    🌏 Asia Pacific                   │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│  │ SPIRE   │   │ SPIRE   │   │ SPIRE   │   ← Резервные серверы  │
│  │ Server  │   │ Server  │   │ Server  │      с failover        │
│  └─────────┘   └─────────┘   └─────────┘                       │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│  │ HNSW    │   │ HNSW    │   │ HNSW    │   ← Replica-aware      │
│  │ Replica │   │ Replica │   │ Replica │     индексация        │
│  └─────────┘   └─────────┘   └─────────┘                       │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│  │ mTLS    │   │ mTLS    │   │ mTLS    │   ← Session resumption │
│  │ Cache   │   │ Cache   │   │ Cache   │     и cert pinning    │
│  └─────────┘   └─────────┘   └─────────┘                       │
├─────────────────────────────────────────────────────────────────┤
│  🔗 BATMAN-adv оптимизированная маршрутизация                  │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│  │ Multi-  │   │ AODV    │   │ Монито- │   ← Multi-path +       │
│  │ Path    │   │ Fallback│   │ ринг    │     fallback          │
│  └─────────┘   └─────────┘   └─────────┘                       │
├─────────────────────────────────────────────────────────────────┤
│  🛡️ Cilium eBPF оптимизированные политики                     │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐                       │
│  │ Consis- │   │ Адаптив-│   │ Монито- │   ← Consistency +      │
│  │ tency   │   │ ные     │   │ ринг    │     снижение ложных   │
│  │ Checks  │   │ политики│   │ политик │     срабатываний      │
│  └─────────┘   └─────────┘   └─────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

## Предварительные требования

### Необходимые инструменты
- Kubernetes 1.27+
- Helm 3.12+
- kubectl с доступом к кластерам
- cert-manager 1.13+
- Prometheus для мониторинга

### Доступ к кластерам
- `us-east-1` - основной регион
- `eu-west-1` - вторичный регион
- `ap-southeast-1` - третичный регион

## Процесс развертывания

### Этап 1: Подготовка инфраструктуры

#### 1.1 Настройка cert-manager для mTLS

```bash
# Развертывание cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Создание ClusterIssuer для корневого CA
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: x0tta6bl4-root-ca
spec:
  ca:
    privateKey:
      algorithm: ECDSA
      size: 256
    validity: 8760h  # 1 год
EOF
```

#### 1.2 Настройка Prometheus мониторинга

```bash
# Создание namespace для мониторинга
kubectl create namespace monitoring

# Развертывание Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

### Этап 2: Развертывание оптимизаций по приоритетам

#### Приоритет 1А: BATMAN-adv оптимизация

```bash
# Переход в директорию оптимизаций
cd infrastructure-optimizations/batman-adv/helm-charts/batman-adv-optimization

# Установка Helm chart
helm install batman-adv-optimization . \
  -n batman-adv-system \
  --create-namespace \
  --set global.imageRegistry=your-registry.com \
  --set batmanAdv.config.multipath.enabled=true \
  --set batmanAdv.config.aodv.enabled=true

# Проверка развертывания
kubectl get pods -n batman-adv-system
kubectl get daemonset -n batman-adv-system
```

#### Приоритет 1Б: SPIFFE/SPIRE резервные серверы

```bash
# Переход в директорию SPIRE оптимизаций
cd infrastructure-optimizations/spiffe-spire/helm-charts/spire-optimization

# Установка Helm chart
helm install spire-optimization . \
  -n spire-system \
  --create-namespace \
  --set spire.global.trustDomain=x0tta6bl4.com \
  --set spire.servers.us-east.enabled=true \
  --set spire.servers.eu-west.enabled=true \
  --set spire.servers.asia-pacific.enabled=true \
  --set spire.agents.edgeAgents.enabled=true \
  --set spire.federation.enabled=true

# Проверка развертывания
kubectl get statefulset -n spire-system
kubectl get daemonset -n spire-system
```

#### Приоритет 1В: HNSW replica-aware индексация

```bash
# Переход в директорию HNSW оптимизаций
cd infrastructure-optimizations/hnsw-indexing/helm-charts/hnsw-replica-optimization

# Установка Helm chart
helm install hnsw-optimization . \
  -n hnsw-system \
  --create-namespace \
  --set hnsw.global.indexName=x0tta6bl4-vector-index \
  --set hnsw.replication.enabled=true \
  --set hnsw.asyncUpdates.enabled=true \
  --set hnsw.localCache.enabled=true \
  --set redis.enabled=true

# Проверка развертывания
kubectl get deployments -n hnsw-system
kubectl get statefulset -n hnsw-system
```

#### Приоритет 2А: mTLS оптимизация

```bash
# Переход в директорию mTLS оптимизаций
cd infrastructure-optimizations/mtls-optimization/helm-charts/mtls-optimization

# Установка Helm chart
helm install mtls-optimization . \
  -n mtls-system \
  --create-namespace \
  --set mtls.global.minTLSVersion=1.3 \
  --set mtls.sessionResumption.enabled=true \
  --set mtls.certificatePinning.enabled=true \
  --set mtls.certManager.enabled=true \
  --set redis.enabled=true

# Проверка развертывания
kubectl get deployments -n mtls-system
kubectl get certificates -n mtls-system
```

#### Приоритет 2Б: Cilium eBPF оптимизация

```bash
# Переход в директорию Cilium оптимизаций
cd infrastructure-optimizations/cilium-ebpf/helm-charts/cilium-ebpf-optimization

# Установка Helm chart
helm install cilium-optimization . \
  -n cilium-system \
  --create-namespace \
  --set cilium.consistencyChecks.enabled=true \
  --set cilium.optimizedPolicies.enabled=true \
  --set cilium.policyMonitoring.enabled=true \
  --set cilium.hubble.enabled=true

# Проверка развертывания
kubectl get pods -n cilium-system -l k8s-app=cilium
kubectl get pods -n cilium-system -l k8s-app=hubble-relay
```

### Этап 3: Валидация развертывания

#### Запуск скриптов валидации

```bash
# BATMAN-adv валидация
cd infrastructure-optimizations/batman-adv/validation-scripts
chmod +x validate-batman-adv-optimizations.sh
./validate-batman-adv-optimizations.sh

# SPIFFE/SPIRE валидация
cd infrastructure-optimizations/spiffe-spire/validation-scripts
chmod +x validate-spire-optimizations.sh
./validate-spire-optimizations.sh

# HNSW валидация
cd infrastructure-optimizations/hnsw-indexing/validation-scripts
chmod +x validate-hnsw-optimizations.sh
./validate-hnsw-optimizations.sh

# mTLS валидация
cd infrastructure-optimizations/mtls-optimization/validation-scripts
chmod +x validate-mtls-optimizations.sh
./validate-mtls-optimizations.sh

# Cilium валидация
cd infrastructure-optimizations/cilium-ebpf/validation-scripts
chmod +x validate-cilium-optimizations.sh
./validate-cilium-optimizations.sh
```

#### Проверка KPI улучшений

```bash
# Мониторинг ключевых метрик
kubectl port-forward -n monitoring svc/prometheus-operated 9090:9090

# Проверка в браузере:
# http://localhost:9090/graph?g0.expr=batman_route_flaps_total&g0.tab=0
# http://localhost:9090/graph?g0.expr=cilium_false_positive_ratio&g0.tab=0
# http://localhost:9090/graph?g0.expr=mtls_handshake_latency_seconds&g0.tab=0
```

## Процедура отката

### Автоматический откат при проблемах

#### 1. Мониторинг алертов

```bash
# Настройка алертов для автоматического отката
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: rollback-alerts
  namespace: monitoring
data:
  alerts.yml: |
    groups:
    - name: infrastructure-rollback
      rules:
      - alert: HighRouteFlaps
        expr: increase(batman_route_flaps_total[5m]) > 50
        for: 5m
        labels:
          severity: critical
          action: rollback
      - alert: HighFalsePositives
        expr: cilium_false_positive_ratio > 0.20
        for: 10m
        labels:
          severity: critical
          action: rollback
EOF
```

#### 2. Автоматический откат скрипт

```bash
#!/bin/bash
# rollback-optimizations.sh

NAMESPACES=(
    "batman-adv-system"
    "spire-system"
    "hnsw-system"
    "mtls-system"
    "cilium-system"
)

RELEASES=(
    "batman-adv-optimization"
    "spire-optimization"
    "hnsw-optimization"
    "mtls-optimization"
    "cilium-optimization"
)

for i in "${!RELEASES[@]}"; do
    echo "Откат релиза ${RELEASES[$i]} в namespace ${NAMESPACES[$i]}"
    helm rollback ${RELEASES[$i]} 0 -n ${NAMESPACES[$i]}
done

echo "Откат завершен. Проверка состояния..."
kubectl get pods --all-namespaces | grep -E "(Error|CrashLoopBackOff|Pending)"
```

### Ручной откат

#### Откат конкретного компонента

```bash
# Откат BATMAN-adv
helm rollback batman-adv-optimization 0 -n batman-adv-system

# Откат SPIFFE/SPIRE
helm rollback spire-optimization 0 -n spire-system

# Откат HNSW
helm rollback hnsw-optimization 0 -n hnsw-system

# Откат mTLS
helm rollback mtls-optimization 0 -n mtls-system

# Откат Cilium
helm rollback cilium-optimization 0 -n cilium-system
```

#### Полный откат всех оптимизаций

```bash
# Удаление всех релизов
helm uninstall batman-adv-optimization -n batman-adv-system
helm uninstall spire-optimization -n spire-system
helm uninstall hnsw-optimization -n hnsw-system
helm uninstall mtls-optimization -n mtls-system
helm uninstall cilium-optimization -n cilium-system

# Удаление namespace'ов
kubectl delete namespace batman-adv-system spire-system hnsw-system mtls-system cilium-system --ignore-not-found=true
```

## Мониторинг и поддержка

### Ключевые метрики для мониторинга

#### BATMAN-adv метрики
- `batman_route_flaps_total` - количество flapping маршрутов
- `batman_multipath_utilization` - использование multi-path
- `batman_neighbor_stability` - стабильность соседей
- `batman_packet_loss_ratio` - потери пакетов

#### SPIFFE/SPIRE метрики
- `spire_token_cache_hit_ratio` - hit ratio кеша токенов
- `spire_failover_events_total` - события failover
- `spire_bundle_sync_duration_seconds` - время синхронизации
- `spire_server_requests_total` - частота запросов

#### HNSW метрики
- `hnsw_search_latency_seconds` - задержка поиска
- `hnsw_cache_hit_rate` - hit rate кеша
- `hnsw_replication_lag_seconds` - задержка репликации
- `hnsw_index_update_latency` - задержка обновления индекса

#### mTLS метрики
- `mtls_handshake_latency_seconds` - задержка handshake
- `mtls_session_resumption_rate` - session resumption rate
- `mtls_certificate_validation_time` - время валидации сертификатов
- `mtls_pinning_violations` - нарушения pinning

#### Cilium метрики
- `cilium_policy_evaluation_seconds` - время оценки политик
- `cilium_false_positive_ratio` - уровень ложных срабатываний
- `cilium_policy_consistency` - консистентность политик
- `cilium_drop_count` - количество дропов

### Графана дашборды

#### Создание дашборда для мониторинга оптимизаций

```bash
# Импорт дашборда в Grafana
kubectl port-forward -n monitoring svc/grafana 3000:3000

# В браузере: http://localhost:3000
# Создать новый дашборд с панелями для ключевых метрик
```

### Регулярные задачи обслуживания

#### Еженедельные проверки
- Валидация всех скриптов оптимизаций
- Проверка логов на наличие ошибок
- Анализ трендов производительности

#### Ежемесячные задачи
- Обновление сертификатов (автоматически через cert-manager)
- Анализ использования ресурсов
- Оптимизация конфигураций на основе метрик

#### Ежеквартальные задачи
- Полное тестирование failover сценариев
- Анализ эффективности оптимизаций
- Планирование следующих фаз оптимизаций

## Troubleshooting

### Общие проблемы и решения

#### Высокий уровень ложных срабатываний Cilium
```bash
# Проверка политик
kubectl exec -n cilium-system cilium-0 -- cilium policy get

# Анализ логов Hubble
kubectl logs -n cilium-system -l k8s-app=hubble-relay --tail=100

# Настройка чувствительности
helm upgrade cilium-optimization ./cilium-ebpf/helm-charts/cilium-ebpf-optimization \
  --set cilium.optimizedPolicies.adaptive.sensitivity=low
```

#### Проблемы с SPIRE failover
```bash
# Проверка статуса серверов
kubectl get statefulset -n spire-system

# Проверка логов агентов
kubectl logs -n spire-system -l app=spire-agent --tail=50

# Проверка федерации
kubectl exec -n spire-system spire-server-0 -- spire-server bundle show
```

#### Низкий hit rate кеша HNSW
```bash
# Проверка Redis кеша
kubectl exec -n hnsw-system hnsw-redis-0 -- redis-cli info memory

# Анализ паттернов запросов
kubectl logs -n hnsw-system deployment/hnsw-indexer --tail=100

# Настройка размера кеша
helm upgrade hnsw-optimization ./hnsw-indexing/helm-charts/hnsw-replica-optimization \
  --set hnsw.localCache.redis.config.maxmemory=15gb
```

### Сбор диагностической информации

#### Скрипт диагностики
```bash
#!/bin/bash
# diagnostics.sh

echo "Сбор диагностической информации..."

# Статус всех компонентов
kubectl get pods --all-namespaces -o wide > pods-status.txt

# Логи ошибок
kubectl logs --all-namespaces --tail=50 -l app | grep -i error > error-logs.txt

# Метрики производительности
kubectl exec -n monitoring prometheus-0 -- \
  curl -s http://localhost:9090/api/v1/query?query=up > prometheus-metrics.txt

# Сетевые политики
kubectl get networkpolicies --all-namespaces -o yaml > network-policies.txt

echo "Диагностика завершена. Файлы созданы."
```

## Следующие шаги

### Фаза 2 (Следующие 2 недели)
- Масштабирование до 100+ регионов
- Интеграция с quantum hardware
- AI-powered автоматическая оптимизация
- Zero-downtime обновления

### Фаза 3 (Следующий квартал)
- Полная автономная инфраструктура
- Предиктивное обслуживание
- Самовосстанавливающиеся системы
- Интеграция с метавселенной

## Поддержка

Для получения помощи и отчетов о проблемах:
- Создайте issue в репозитории инфраструктуры
- Используйте Slack канал #infrastructure-optimization
- Напишите в email: infrastructure@x0tta6bl4.com

---

*Последнее обновление: $(date)*
*Версия документа: 1.0.0*