# Kubernetes Deployment

## Prerequisites

- Kubernetes 1.28+
- Helm 3.0+
- kubectl configured

## Quick Install

```bash
helm install x0tta6bl4 ./helm/x0tta6bl4 \
  --namespace mesh-system \
  --create-namespace
```

## Production Install

```bash
helm install x0tta6bl4 ./helm/x0tta6bl4 \
  --namespace mesh-system \
  --create-namespace \
  --set replicaCount=3 \
  --set autoscaling.enabled=true \
  --set monitoring.enabled=true
```

## Verify

```bash
# Check pods
kubectl get pods -n mesh-system

# Check service
kubectl get svc -n mesh-system

# Port forward
kubectl port-forward -n mesh-system svc/x0tta6bl4 8080:8080
```

## Configuration

See `values.yaml` for all options:

```yaml
replicaCount: 3

mesh:
  slotDuration: 100
  beaconInterval: 5

security:
  pqCrypto:
    enabled: true

ai:
  enabled: true
  quantization: INT8

dao:
  enabled: true
  quadraticVoting: true
```
