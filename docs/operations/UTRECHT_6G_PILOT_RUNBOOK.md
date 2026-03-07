# Utrecht 6G Pilot Runbook

## Purpose
Operational runbook for provisioning and validating the Utrecht 6G pilot mesh.

## Artifacts
- `scripts/ops/utrecht_6g_deploy.py`
- `values-utrecht.yaml`
- `utrecht-deploy-manifest.yaml`

## Preflight
1. Ensure staging stack is up:
```bash
make status
```
2. Validate service health:
```bash
make test
```
3. Preview pilot provisioning request:
```bash
make utrecht-plan
```

## Provision Pilot Mesh
Default deployment (reads `values-utrecht.yaml`):
```bash
make utrecht-deploy
```

Manual override example:
```bash
python3 scripts/ops/utrecht_6g_deploy.py \
  --values-file values-utrecht.yaml \
  --nodes 20 \
  --billing-plan enterprise \
  --output json
```

## Apply Kubernetes Agent Manifest
Preview differences:
```bash
make utrecht-manifest-diff
```

Apply:
```bash
make utrecht-manifest-apply
```

## Validation Checklist
1. `make test` returns healthy API/DB/Redis/Prometheus/Grafana.
2. `make agent-cycle` completes with `agent-1..4 rc=0`.
3. `make utrecht-plan` shows expected node count/plan/region.

## Daily Observation Loop (7-14 days)
Run once per day during the pilot observation window:
```bash
make utrecht-observation
```

Review recent entries:
```bash
make utrecht-observation-tail
```

Artifacts are stored in:
- `docs/governance/proposals/UTRECHT_PILOT_OBSERVATION_LOG.md`
- `docs/governance/proposals/utrecht-observations/*.log`

Generate governance artifacts from accumulated observations:
```bash
make utrecht-kpi-summary
make utrecht-funding-draft
```

## Rollback
1. Stop pilot resources:
```bash
kubectl delete -f utrecht-deploy-manifest.yaml
```
2. Re-check core staging health:
```bash
make status && make test
```
