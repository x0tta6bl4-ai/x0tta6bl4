# Chaos Engineering Tests

Сценарии для проверки устойчивости mesh-сети к сбоям.

## Prerequisites

```bash
# Install Chaos Mesh
kubectl apply -f https://mirrors.chaos-mesh.org/v2.7.0/crd.yaml
kubectl apply -f https://mirrors.chaos-mesh.org/v2.7.0/chaos-mesh.yaml

# Verify installation
kubectl get pods -n chaos-mesh
```

## Test Scenarios

### 1. Pod Kill (25%)
```bash
kubectl apply -f chaos/pod-kill-25pct.yaml
```
**Target:** MTTR ≤ 5 seconds

### 2. Network Delay (100-500ms)
```bash
kubectl apply -f chaos/network-delay.yaml
```
**Target:** No degradation in functionality

### 3. Network Partition (50%)
```bash
kubectl apply -f chaos/partition-50pct.yaml
```
**Target:** Both partitions continue operating

## Expected Results

| Scenario | Metric | Target | Pass Criteria |
|----------|--------|--------|---------------|
| Pod Kill 25% | MTTR | ≤5s | Recovery in <5 seconds |
| Pod Kill 25% | Success Rate | ≥98% | 98+ pods recover |
| Network Delay | Packet Loss | ≤0.2% | During failover |
| Partition 50% | Connectivity | ≥95% | Each partition works |
| DNS Error | Resolution | ≥90% | Fallback works |

## Cleanup

```bash
kubectl delete -f chaos/
```

## Integration with CI

```yaml
# .github/workflows/chaos-test.yml
- name: Run Chaos Tests
  run: |
    kubectl apply -f chaos/pod-kill-25pct.yaml
    sleep 70  # Wait for chaos + recovery
    ./scripts/validate_mttr.sh
```
