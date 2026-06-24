# Infrastructure Overview

Unified infrastructure layout introduced during restructuring (Phase 2). This directory hosts provisioning, deployment and runtime topology assets. Each sub‑directory is intentionally single‑responsibility.

```
infra/
  terraform/   # Cloud infra & base networking / state backends
  networking/  # Mesh (batman-adv), eBPF probes, routing helpers
  security/    # SPIFFE/SPIRE, trust bundle mgmt, mTLS policies
  k8s/         # Kubernetes manifests (staging/prod overlays)
  docker/      # Dockerfiles, build args, multi-stage images
  helm/        # Helm charts / value overrides (optional)
```

---
## 🔁 Recommended Apply Order
| Step | Layer | Directory | Purpose |
|------|-------|-----------|---------|
| 1 | Foundation | `terraform/` | Networking, clusters, storage, PKI anchors |
| 2 | Identity Plane | `security/` | SPIRE server/agents, trust bundle distribution |
| 3 | Mesh Overlay | `networking/` | batman-adv bootstrap, eBPF observability |
| 4 | Runtime Workloads | `k8s/` | Core services, control loop, ML components |
| 5 | Packaging (optional) | `helm/` | Chart-driven templated deployments |
| 6 | Container Builds | `docker/` | Deterministic runtime images |

---
## 🌐 Terraform
- Backend state: (configure remote backend before collaborative apply)
- Workspace strategy: environment separation (`staging`, `prod`)
- Outputs consumed by:
  - SPIRE server endpoints
  - Mesh peer seeds / initial node list
  - Observability endpoints (Prometheus / tracing collector)

### Example
```bash
cd infra/terraform
terraform init
terraform plan -var env=staging
terraform apply -var env=staging
```

---
## 🔐 Security (SPIFFE/SPIRE)
| Component | Role |
|-----------|------|
| SPIRE Server | Issues SVIDs, manages registration entries |
| SPIRE Agent | Node attestation + workload API |
| Trust Bundle | Distributed for mTLS validation |

Roadmap enhancements:
- Automated cert rotation controller
- Policy audit exporter

---
## 🕸 Networking
Includes configuration and helper scripts for:
- batman-adv mesh formation
- Link quality (TQ) monitoring hooks
- Optional eBPF programs for packet path tracing / congestion observation

Metrics exported to Prometheus (planned dashboards):
- Mesh node degree
- Path selection churn
- Retransmission ratios

---
## ☸ Kubernetes Manifests
Suggested layout (if not already present):
```
k8s/
  base/              # Shared definitions
  overlays/
    staging/
    prod/
```
Apply:
```bash
kubectl apply -k infra/k8s/overlays/staging/
```

---
## 🐳 Docker
- Multi-stage builds for minimal runtime images
- Reproducible by pinning builder image digests
- Security: avoid adding build tools to final stage

Example:
```bash
docker build -f infra/docker/Dockerfile -t x0tta6bl4:dev .
```

---
## ⎈ Helm (Optional)
If using Helm for environment templating:
- Values layering: `values.yaml` (base) + `values-staging.yaml` + `values-prod.yaml`
- Integrate with GitHub Actions release pipeline for chart packaging (future)

---
## 📊 Observability Integration Points
| Layer | Metrics / Traces |
|-------|------------------|
| Control Loop | Cycle duration histograms |
| Networking | Path switch counters, link health |
| Security | SVID issuance / renewal events |
| ML | Embedding latency, retrieval hit ratio |

---
## 🧪 Validation Checklist (Post Apply)
- [ ] All nodes registered with SPIRE
- [ ] Mesh adjacency graph stable (< X churn / min)
- [ ] Prometheus scrape targets healthy
- [ ] mTLS handshakes < 50ms p95
- [ ] Vector index warm preloading (if enabled)

---
## 🗺 Future Enhancements
| Area | Idea |
|------|------|
| Terraform | Drift detection automation |
| Networking | Dynamic channel rebalancing via eBPF feedback loop |
| Security | Federated CA trust bridging |
| K8s | Progressive delivery (Argo / Flagger) |
| Docker | SBOM generation + attestation |
| Helm | Versioned environment bundles |

---
*Keep infrastructure PRs small and auditable; prefer declarative state, avoid brittle scripting.*
