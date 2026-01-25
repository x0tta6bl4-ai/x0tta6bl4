# Chaos Testing

x0tta6bl4 includes built-in chaos engineering tests.

## Pod Kill Test

Tests Kubernetes self-healing capability.

```bash
./scripts/chaos-pod-kill.sh
```

Expected result:
- **MTTR**: ≤5 seconds
- **Recovery rate**: 100%

### Results from v3.0.0

| Scenario | Target | Achieved |
|----------|--------|----------|
| Pod Kill 25% | ≤5s | **2.79s** ✅ |
| Pod Kill 50% | ≤5s | **<5s** ✅ |

## Network Delay Test

```bash
kubectl apply -f chaos/network-delay.yaml
```

Injects 100ms latency to test system resilience.

## Network Partition Test

```bash
kubectl apply -f chaos/partition-50pct.yaml
```

Simulates split-brain scenario.

## Custom Chaos

Create your own chaos experiments:

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: custom-chaos
spec:
  action: pod-kill
  mode: fixed-percent
  value: "25"
  selector:
    labelSelectors:
      app: x0tta6bl4
```
