# mTLS Configuration for x0tta6bl4

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                       mTLS Architecture                         │
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │ cert-manager│    │    SPIRE    │    │   Istio     │        │
│  │  (CA PKI)   │    │  (SPIFFE)   │    │   (mesh)    │        │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘        │
│         │                  │                   │               │
│         └──────────────────┼───────────────────┘               │
│                            │                                   │
│                   ┌────────▼────────┐                         │
│                   │   Workloads     │                         │
│                   │  with mTLS      │                         │
│                   └─────────────────┘                         │
│                                                                │
│  Certificate Flow:                                             │
│  1. SPIRE issues SVID (SPIFFE ID + X.509 cert)               │
│  2. cert-manager manages lifecycle                            │
│  3. Istio enforces mTLS policies                              │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Компоненты

### 1. cert-manager

Управление PKI инфраструктурой:
- Root CA (10 лет)
- Intermediate CA (1 год)
- Workload сертификаты (30 дней)

```bash
# Установка cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Применение ClusterIssuers
kubectl apply -f infra/mtls/cert-manager/
```

### 2. SPIFFE/SPIRE

Workload Identity с автоматической аттестацией:
- Trust Domain: `x0tta6bl4.mesh`
- SVID TTL: 1 час
- JWT TTL: 5 минут

```bash
# SPIRE уже установлен, применить регистрации
kubectl apply -f infra/mtls/spire/
```

### 3. Istio mTLS

Service mesh с STRICT mTLS:
- Production: STRICT mode
- Staging: PERMISSIVE mode
- Metrics endpoints: PERMISSIVE

## Установка

```bash
# Предварительные требования
kubectl create namespace x0tta6bl4-production
kubectl create namespace x0tta6bl4-staging

# Применить все mTLS ресурсы
kubectl apply -k infra/mtls/
```

## Использование в приложении

### Python (aiohttp)

```python
from src.security.mtls_client import MTLSClient, mtls_request

# Как context manager
async with MTLSClient() as client:
    response = await client.get("https://service.internal/api/v1/data")
    data = await response.json()

# Или через helper
async with mtls_request("https://service.internal/api/v1/data") as response:
    data = await response.json()
```

### Конфигурация через Environment

```yaml
env:
  - name: MTLS_CERT_PATH
    value: /etc/certs/tls.crt
  - name: MTLS_KEY_PATH
    value: /etc/certs/tls.key
  - name: MTLS_CA_PATH
    value: /etc/certs/ca.crt
  - name: SPIFFE_ENDPOINT_SOCKET
    value: /run/spire/sockets/agent.sock
```

### Kubernetes Deployment

```yaml
spec:
  containers:
    - name: proxy-api
      volumeMounts:
        - name: spiffe-socket
          mountPath: /run/spire/sockets
          readOnly: true
        - name: tls-certs
          mountPath: /etc/certs
          readOnly: true
  volumes:
    - name: spiffe-socket
      hostPath:
        path: /run/spire/sockets
        type: DirectoryOrCreate
    - name: tls-certs
      secret:
        secretName: proxy-api-tls
```

## Верификация

### Проверка сертификатов

```bash
# Статус cert-manager сертификатов
kubectl get certificates -n x0tta6bl4-production

# Детали сертификата
kubectl describe certificate proxy-api-tls -n x0tta6bl4-production

# Проверка секрета
kubectl get secret proxy-api-tls -n x0tta6bl4-production -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout
```

### Проверка SPIRE

```bash
# Список зарегистрированных workloads
kubectl exec -n spire-system spire-server-0 -- \
  /opt/spire/bin/spire-server entry show

# Проверка SVID
kubectl exec -it deploy/proxy-api -n x0tta6bl4-production -- \
  cat /run/spire/sockets/svid.pem | openssl x509 -text -noout
```

### Проверка Istio mTLS

```bash
# Статус mTLS
istioctl authn tls-check proxy-api.x0tta6bl4-production

# PeerAuthentication
kubectl get peerauthentication -n x0tta6bl4-production

# AuthorizationPolicy
kubectl get authorizationpolicy -n x0tta6bl4-production
```

## Мониторинг

### Prometheus метрики

```promql
# Успешные mTLS handshakes
sum(rate(istio_tcp_connections_opened_total{
  connection_security_policy="mutual_tls"
}[5m])) by (destination_service)

# Ошибки TLS
sum(rate(istio_tcp_connections_closed_total{
  connection_security_policy="unknown"
}[5m])) by (destination_service)

# Срок действия сертификатов
certmanager_certificate_expiration_timestamp_seconds - time()
```

### Alerting

```yaml
- alert: CertificateExpiringSoon
  expr: certmanager_certificate_expiration_timestamp_seconds - time() < 604800
  labels:
    severity: warning
  annotations:
    summary: "Certificate expires in less than 7 days"

- alert: MTLSPolicyViolation
  expr: increase(istio_tcp_connections_closed_total{connection_security_policy="unknown"}[5m]) > 0
  labels:
    severity: critical
  annotations:
    summary: "Non-mTLS connection detected"
```

## Troubleshooting

### Ошибка "certificate verify failed"

```bash
# Проверить CA bundle
kubectl get secret x0tta6bl4-intermediate-ca-secret -n cert-manager -o yaml

# Проверить trust store в поде
kubectl exec -it deploy/proxy-api -- \
  openssl verify -CAfile /etc/certs/ca.crt /etc/certs/tls.crt
```

### Ошибка "SPIFFE socket not found"

```bash
# Проверить SPIRE agent
kubectl get daemonset -n spire-system spire-agent

# Проверить socket на ноде
kubectl debug node/<node-name> -it --image=busybox -- \
  ls -la /run/spire/sockets/
```

### Ошибка "connection refused" при mTLS

```bash
# Проверить Istio sidecar
istioctl proxy-status

# Проверить DestinationRule
kubectl get destinationrule -n x0tta6bl4-production -o yaml
```

## Ротация сертификатов

### Автоматическая (cert-manager)

cert-manager автоматически обновляет сертификаты за 7 дней до истечения.

### Ручная ротация

```bash
# Удалить секрет для принудительного обновления
kubectl delete secret proxy-api-tls -n x0tta6bl4-production

# cert-manager создаст новый сертификат
kubectl get certificate proxy-api-tls -n x0tta6bl4-production -w
```

### Ротация Root CA

```bash
# 1. Создать новый Root CA
kubectl apply -f infra/mtls/cert-manager/new-root-ca.yaml

# 2. Обновить trust bundles
kubectl rollout restart deployment -n x0tta6bl4-production

# 3. Удалить старый CA после ротации всех сертификатов
```
