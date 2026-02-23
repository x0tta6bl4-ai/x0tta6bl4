# Istio-like WAN Overlay Profile for x0tta6bl4 MaaS

Этот набор манифестов задаёт безопасный baseline для service-mesh поведения:
- mTLS (STRICT)
- zero-trust L7 policy на уровне namespace/workload
- retries/timeouts/circuit-breaker (outlier detection)
- canary split для контролируемого rollout

## Quick Apply

```bash
kubectl apply -f deploy/k8s/istio-like/namespace-and-labels.yaml
kubectl apply -f deploy/k8s/istio-like/peer-authn.yaml
kubectl apply -f deploy/k8s/istio-like/destination-rules.yaml
kubectl apply -f deploy/k8s/istio-like/virtual-services.yaml
```

## Assumptions

- Istio control-plane уже установлен в кластере.
- Namespace для MaaS workloads: `x0tta6bl4`.
- Service имена:
  - `x0tta6bl4-api`
  - `x0tta6bl4-worker`

Если у вас другие service/namespace имена, замените `host`/`namespace`.

## Why This Helps (80/20)

- Даёт быстрый zero-trust baseline без глубокого рефакторинга приложения.
- Уменьшает blast radius при деградации endpoint'ов через outlier ejection.
- Позволяет safe rollout новых версий API (stable/canary 90/10).
