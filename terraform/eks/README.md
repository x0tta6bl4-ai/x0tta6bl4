# x0tta6bl4 EKS Terraform Module

Production-ready AWS EKS cluster for x0tta6bl4 mesh network.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AWS Region (us-east-1)                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    VPC (10.0.0.0/16)                 │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Public Subnets     │  Private Subnets              │   │
│  │  ┌───────────────┐  │  ┌────────────────────────┐   │   │
│  │  │ NAT Gateway   │  │  │ EKS Node Groups        │   │   │
│  │  │ Load Balancer │  │  │ ├─ mesh-control (2)    │   │   │
│  │  └───────────────┘  │  │ ├─ mesh-workers (3)    │   │   │
│  │                     │  │ └─ mesh-monitoring (2) │   │   │
│  │                     │  └────────────────────────┘   │   │
│  └─────────────────────┴───────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                 EKS Control Plane                    │   │
│  │  • Version: 1.30                                     │   │
│  │  • IRSA enabled (Zero Trust pod identity)            │   │
│  │  • Audit logging enabled                             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.7.0
- kubectl

### Deployment

```bash
# 1. Copy example vars
cp terraform.tfvars.example terraform.tfvars

# 2. Edit terraform.tfvars (set your IP for allowed_cidr_blocks)
vim terraform.tfvars

# 3. Initialize
terraform init

# 4. Plan
terraform plan -out=tfplan

# 5. Apply (~15-20 min)
terraform apply tfplan

# 6. Configure kubectl
$(terraform output -raw kubeconfig_command)

# 7. Verify
kubectl get nodes
```

## Node Groups

| Group | Purpose | Type | Count | Capacity |
|-------|---------|------|-------|----------|
| mesh-control | SPIRE, critical | t3.medium | 1-3 | ON_DEMAND |
| mesh-workers | Data plane | t3.large | 2-10 | SPOT (staging) |
| mesh-monitoring | Prometheus, Grafana | t3.xlarge | 1-3 | ON_DEMAND |

## Cost Estimate (Staging)

| Component | Cost/Month |
|-----------|------------|
| EKS Control Plane | $73 |
| Control Nodes (2x t3.medium) | ~$60 |
| Worker Nodes (3x t3.large SPOT) | ~$60 |
| Monitoring Nodes (2x t3.xlarge) | ~$120 |
| NAT Gateway | ~$32 |
| EBS Storage (250GB) | ~$25 |
| **Total** | **~$370/month** |

## Outputs

```bash
# Get cluster name
terraform output cluster_name

# Get kubeconfig command
terraform output kubeconfig_command

# Get Grafana port-forward command
terraform output grafana_port_forward
```

## Security

- ✅ Private endpoint access
- ✅ Control plane audit logging
- ✅ IRSA for pod identity (Zero Trust)
- ✅ VPC CNI with network policies
- ⚠️ Restrict `allowed_cidr_blocks` in production!

## Cleanup

```bash
terraform destroy
```

## Related Files

- `argocd/applications/spire.yaml` - SPIRE GitOps
- `argocd/applications/monitoring.yaml` - Prometheus/Grafana GitOps
- `infra/k8s/kind-local/` - Local Kind manifests (portable to EKS)
