# Руководство по развертыванию Multi-Region инфраструктуры x0tta6bl4

## Обзор

Данная документация описывает процесс развертывания и эксплуатации многорегиональной инфраструктуры проекта x0tta6bl4 с высокой доступностью и disaster recovery возможностями.

## Архитектура

### Регионы
- **us-east-1** (Северная Америка) - Основной регион
- **eu-west-1** (Европа) - Реплика для EMEA
- **ap-southeast-1** (Азия-Пасифик) - Реплика для APAC

### Компоненты
- **Глобальный Load Balancer** (Cloudflare) - Географическое распределение трафика
- **Региональные EKS кластеры** - Kubernetes в каждом регионе
- **Глобальная база данных Aurora** - Кросс-региональная репликация
- **Мониторинг и алертинг** - Prometheus, Grafana, CloudWatch
- **Disaster Recovery** - Автоматический failover между регионами

## Предварительные требования

### Необходимое ПО
- Terraform >= 1.0
- AWS CLI настроенный
- kubectl >= 1.25
- Helm >= 3.0
- Git

### Доступы и разрешения
- AWS аккаунт с правами администратора
- Cloudflare аккаунт с API токеном
- Домен x0tta6bl4.com настроенный в Cloudflare

## Быстрое развертывание

### Шаг 1: Клонирование репозитория
```bash
git clone <repository-url>
cd multi-region-infrastructure
```

### Шаг 2: Настройка переменных
```bash
# Копирование примера файла переменных
cp terraform/global/terraform.tfvars.example terraform/global/terraform.tfvars

# Редактирование файла с вашими значениями
nano terraform/global/terraform.tfvars
```

### Шаг 3: Развертывание глобальной инфраструктуры
```bash
cd terraform/global

# Инициализация Terraform
terraform init

# Планирование изменений
terraform plan

# Применение конфигурации
terraform apply
```

### Шаг 4: Развертывание региональных ресурсов

#### us-east-1 (основной регион)
```bash
cd ../us-east-1

# Инициализация
terraform init

# Развертывание
terraform plan
terraform apply
```

#### eu-west-1 (регион реплика)
```bash
cd ../eu-west-1

terraform init
terraform plan
terraform apply
```

#### ap-southeast-1 (регион реплика)
```bash
cd ../ap-southeast-1

terraform init
terraform plan
terraform apply
```

### Шаг 5: Настройка Kubernetes доступа

#### Обновление kubeconfig для каждого региона
```bash
# us-east-1
aws eks update-kubeconfig --region us-east-1 --name x0tta6bl4-us-east-1

# eu-west-1
aws eks update-kubeconfig --region eu-west-1 --name x0tta6bl4-eu-west-1

# ap-southeast-1
aws eks update-kubeconfig --region ap-southeast-1 --name x0tta6bl4-ap-southeast-1
```

### Шаг 6: Развертывание глобальных Kubernetes ресурсов
```bash
# Переход в директорию с глобальными манифестами
cd ../../kubernetes/global

# Развертывание базовых ресурсов
kubectl apply -f base/

# Развертывание Istio сервис-меша
kubectl apply -f istio/

# Развертывание мониторинга
kubectl apply -f monitoring/
```

### Шаг 7: Развертывание региональных приложений

#### us-east-1
```bash
cd ../us-east-1

# Создание namespace
kubectl apply -f base/namespace.yaml --context=x0tta6bl4-us-east-1

# Развертывание приложения
kubectl apply -f app/ --context=x0tta6bl4-us-east-1

# Развертывание мониторинга
kubectl apply -f monitoring/ --context=x0tta6bl4-us-east-1
```

#### eu-west-1
```bash
cd ../eu-west-1

kubectl apply -f base/namespace.yaml --context=x0tta6bl4-eu-west-1
kubectl apply -f app/ --context=x0tta6bl4-eu-west-1
kubectl apply -f monitoring/ --context=x0tta6bl4-eu-west-1
```

#### ap-southeast-1
```bash
cd ../ap-southeast-1

kubectl apply -f base/namespace.yaml --context=x0tta6bl4-ap-southeast-1
kubectl apply -f app/ --context=x0tta6bl4-ap-southeast-1
kubectl apply -f monitoring/ --context=x0tta6bl4-ap-southeast-1
```

## Верификация развертывания

### Проверка состояния кластеров
```bash
# Проверка узлов в каждом кластере
kubectl get nodes --context=x0tta6bl4-us-east-1
kubectl get nodes --context=x0tta6bl4-eu-west-1
kubectl get nodes --context=x0tta6bl4-ap-southeast-1

# Проверка подов
kubectl get pods -A --context=x0tta6bl4-us-east-1
kubectl get pods -A --context=x0tta6bl4-eu-west-1
kubectl get pods -A --context=x0tta6bl4-ap-southeast-1
```

### Проверка баз данных
```bash
# Проверка состояния глобального кластера
aws rds describe-db-clusters --region us-east-1 --db-cluster-identifier x0tta6bl4-global

# Проверка репликации
aws rds describe-db-cluster-endpoints --region us-east-1 --db-cluster-identifier x0tta6bl4-global
```

### Проверка мониторинга
```bash
# Проверка Prometheus
kubectl port-forward -n monitoring-us-east-1 svc/prometheus-operated 9090:9090

# Проверка Grafana
kubectl port-forward -n monitoring-us-east-1 svc/grafana 3000:3000
```

## Эксплуатация

### Мониторинг и алертинг

#### Доступ к Grafana
- URL: https://grafana.us-east-1.x0tta6bl4.com
- Логин: admin
- Пароль: (из Secrets Manager секрета `x0tta6bl4-us-east-1-grafana-password`)

#### Основные дашборды
- **x0tta6bl4 Overview** - Общий обзор системы
- **Regional Performance** - Производительность по регионам
- **Database Metrics** - Метрики базы данных
- **Infrastructure Health** - Здоровье инфраструктуры

### Масштабирование

#### Автоматическое масштабирование
```bash
# Проверка HPA
kubectl get hpa -A --context=x0tta6bl4-us-east-1

# Ручное масштабирование
kubectl scale deployment x0tta6bl4-app --replicas=5 -n x0tta6bl4-us-east-1
```

#### Масштабирование базы данных
```bash
# Добавление read replica
aws rds create-db-cluster-endpoint \
  --region us-east-1 \
  --db-cluster-identifier x0tta6bl4-global \
  --db-cluster-endpoint-identifier x0tta6bl4-reader \
  --endpoint-type reader
```

### Обновления

#### Обновление приложения
```bash
# Сборка нового образа
docker build -t x0tta6bl4/app:latest .

# Загрузка в registry
docker push x0tta6bl4/app:latest

# Обновление deployment
kubectl rollout restart deployment/x0tta6bl4-app -n x0tta6bl4-us-east-1
```

#### Обновление Kubernetes кластера
```bash
# Обновление версии кластера
aws eks update-cluster-version \
  --region us-east-1 \
  --name x0tta6bl4-us-east-1 \
  --kubernetes-version 1.28

# Обновление node groups
aws eks update-nodegroup-version \
  --region us-east-1 \
  --cluster-name x0tta6bl4-us-east-1 \
  --nodegroup-name x0tta6bl4-us-east-1-main
```

## Disaster Recovery

### Тестирование failover
```bash
# Запуск FIS эксперимента
aws fis start-experiment \
  --experiment-template-id $(terraform output -raw disaster_recovery_plan_id) \
  --region us-east-1

# Мониторинг процесса
aws fis get-experiment --id <experiment-id> --region us-east-1
```

### Восстановление из бэкапа
```bash
# Восстановление базы данных
aws rds restore-db-cluster-to-point-in-time \
  --region us-east-1 \
  --db-cluster-identifier x0tta6bl4-restored \
  --source-db-cluster-identifier x0tta6bl4-global \
  --restore-to-time 2024-01-01T00:00:00Z

# Восстановление из S3 бэкапа
aws backup start-restore-job \
  --recovery-point-arn <recovery-point-arn> \
  --metadata '{"Name":"x0tta6bl4-restored"}' \
  --region us-east-1
```

## Безопасность

### Управление секретами
```bash
# Получение пароля базы данных
aws secretsmanager get-secret-value \
  --secret-id x0tta6bl4-global-db-password \
  --region us-east-1

# Получение пароля Grafana
aws secretsmanager get-secret-value \
  --secret-id x0tta6bl4-us-east-1-grafana-password \
  --region us-east-1
```

### Аудит доступа
```bash
# Проверка CloudTrail логов
aws cloudtrail lookup-events \
  --region us-east-1 \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateUser

# Проверка EKS audit логов
kubectl logs -n kube-system deployment/aws-for-fluent-bit --context=x0tta6bl4-us-east-1
```

## Производительность

### Оптимизация
```bash
# Включение ускорения CloudFront
aws cloudfront create-distribution \
  --distribution-config file://cloudfront-config.json \
  --region us-east-1

# Настройка кеширования Redis
aws elasticache modify-replication-group \
  --region us-east-1 \
  --replication-group-id x0tta6bl4-us-east-1 \
  --apply-immediately \
  --parameter-group-name custom-redis-params
```

### Мониторинг производительности
```bash
# Метрики ALB
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value=<lb-arn> \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 300 \
  --statistics Average \
  --region us-east-1
```

## Стоимость

### Мониторинг расходов
```bash
# Проверка расходов по сервисам
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --region us-east-1

# Настройка бюджетов
aws budgets create-budget \
  --budget file://budget-config.json \
  --region us-east-1
```

## Поддержка

### Контакты команды
- **DevOps**: devops@x0tta6bl4.com
- **Security**: security@x0tta6bl4.com
- **Support**: support@x0tta6bl4.com

### Эскалация инцидентов
1. Проверить статус сервисов в Grafana
2. Проверить алерты в Slack #alerts
3. Создать инцидент в Jira
4. Эскалировать дежурному инженеру

### Полезные ссылки
- [Grafana Dashboard](https://grafana.us-east-1.x0tta6bl4.com)
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/)
- [Route53 Console](https://console.aws.amazon.com/route53/)
- [EKS Console](https://console.aws.amazon.com/eks/)

## Заключение

Поздравляем! Вы успешно развернули многорегиональную инфраструктуру x0tta6bl4 с высокой доступностью и disaster recovery возможностями. Система готова к эксплуатации в production среде.

Для получения дополнительной информации обращайтесь к документации в директории `docs/` или к команде DevOps.