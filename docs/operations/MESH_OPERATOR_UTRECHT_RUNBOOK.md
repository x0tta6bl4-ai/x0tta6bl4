# Mesh Operator Utrecht Runbook

## Goal
Deploy and validate `x0tta-mesh-operator` for the Utrecht pilot profile.

## Files
- `charts/x0tta-mesh-operator/`
- `deploy/helm/values-x0tta-mesh-operator-utrecht.yaml`
- `scripts/ops/mesh_operator_health.py`
- `scripts/ops/kubectl_safe.sh`
- `Makefile` targets: `mesh-operator-*`

## Preflight
1. Verify cluster context:
```bash
kubectl config current-context
```
2. Verify Helm:
```bash
helm version --short
```
3. Lint chart with pilot values:
```bash
make mesh-operator-lint
```
4. Run automated preflight:
```bash
make mesh-operator-preflight
```

Note: `mesh-operator-*` targets use `scripts/ops/helm_safe.sh`.
If local Helm is blocked (for example snap confinement), it auto-falls back to dockerized Helm.
Override image if needed:
```bash
HELM_IMAGE=alpine/helm:3.15.4 make mesh-operator-lint
```
For `kubectl`, targets use `scripts/ops/kubectl_safe.sh` (same fallback pattern).

## Plan
Render manifests before apply:
```bash
make mesh-operator-plan
```

## Install / Upgrade
Install:
```bash
make mesh-operator-install
```

Upgrade:
```bash
make mesh-operator-upgrade
```

Optional overrides:
```bash
make mesh-operator-install \
  MESH_OPERATOR_RELEASE=x0tta-mesh \
  MESH_OPERATOR_NAMESPACE=x0tta-mesh-system \
  MESH_OPERATOR_VALUES=deploy/helm/values-x0tta-mesh-operator-utrecht.yaml
```

## Validate
Run smoke checks:
```bash
make mesh-operator-smoke
```

Manual verification:
1. Operator pod is ready:
```bash
kubectl get pods -n x0tta-mesh-system
```
2. CRD is installed:
```bash
kubectl get crd meshclusters.x0tta6bl4.io
```
3. Service is reachable:
```bash
kubectl get svc -n x0tta-mesh-system
```

## Rollback
```bash
make mesh-operator-uninstall
kubectl delete namespace x0tta-mesh-system --ignore-not-found
```
