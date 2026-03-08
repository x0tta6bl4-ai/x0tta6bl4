# x0tta6bl4 MaaS — Installation Guide

**Version:** v1.0.0 | **Requirements:** Kubernetes 1.28+, Helm 3.14+

---

## Quick Start (single command)

```bash
kubectl apply -f https://releases.x0tta6bl4.io/v1.0.0/all-in-one.yaml
```

Edit secrets before applying — see [Secrets](#secrets).

---

## Option A: Helm (Recommended)

### 1. Add the Helm registry

```bash
helm registry login registry.gitlab.com --username <gitlab-user> --password <token>
```

### 2. Install with enterprise values

```bash
helm upgrade --install x0tta oci://registry.gitlab.com/x0tta/charts/x0tta6bl4-commercial \
  --version 1.0.0 \
  --namespace x0tta-production \
  --create-namespace \
  --values charts/x0tta6bl4-commercial/values-enterprise.yaml \
  --set global.imageTag=v1.0.0 \
  --set externalDatabase.host=<YOUR_PG_HOST> \
  --set x0tta-secrets.jwtSecret=<32_CHAR_SECRET> \
  --wait --timeout=15m
```

### 3. Verify

```bash
kubectl get pods -n x0tta-production
kubectl run smoke --image=curlimages/curl --rm -it --restart=Never \
  -- curl http://mesh-api.x0tta-production.svc/mesh/topology
```

---

## Option B: Terraform (AWS EKS)

```hcl
module "x0tta_eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "x0tta-production"
  cluster_version = "1.28"
  vpc_id          = var.vpc_id
  subnet_ids      = var.private_subnets

  eks_managed_node_groups = {
    mesh_nodes = {
      instance_types = ["c6i.xlarge"]   # 4 vCPU, 8GB RAM
      min_size       = 3
      max_size       = 20
      desired_size   = 5
      labels = { "x0tta.io/mesh-role" = "relay" }
    }
    edge_arm = {
      instance_types = ["m7g.large"]    # Graviton3 arm64
      min_size       = 1
      max_size       = 10
      desired_size   = 2
      ami_type       = "AL2_ARM_64"
    }
  }
}

resource "helm_release" "x0tta" {
  name       = "x0tta"
  repository = "oci://registry.gitlab.com/x0tta/charts"
  chart      = "x0tta6bl4-commercial"
  version    = "1.0.0"
  namespace  = "x0tta-production"

  values = [file("values-enterprise.yaml")]

  set { name = "global.imageTag";         value = "v1.0.0" }
  set { name = "externalDatabase.host";   value = aws_db_instance.pg.address }
  set_sensitive { name = "x0tta-secrets.jwtSecret"; value = var.jwt_secret }
}
```

---

## Option C: Ansible (Bare Metal / On-Prem)

```yaml
# playbooks/install-x0tta.yml
- name: Deploy x0tta6bl4 MaaS
  hosts: k8s-masters
  become: true
  tasks:
    - name: Add Helm repo
      command: helm registry login registry.gitlab.com -u "{{ gitlab_user }}" -p "{{ gitlab_token }}"

    - name: Deploy x0tta
      command: |
        helm upgrade --install x0tta \
          oci://registry.gitlab.com/x0tta/charts/x0tta6bl4-commercial \
          --version 1.0.0 \
          --namespace x0tta-production \
          --create-namespace \
          --set global.imageTag=v1.0.0 \
          --values /tmp/values-enterprise.yaml \
          --wait --timeout=15m

    - name: Verify deployment
      command: kubectl get pods -n x0tta-production
      register: pods
    - debug: var=pods.stdout_lines
```

---

## Secrets

Replace placeholder values before deploying:

| Secret Key | Description |
|-----------|-------------|
| `jwt-secret` | 32+ character random string for JWT signing |
| `redis-url` | Redis connection URL with auth |
| `db-url` | PostgreSQL connection string |
| `dao-executor-pk` | 0x-prefixed private key for on-chain governance (optional) |

Generate a secure JWT secret:
```bash
openssl rand -hex 32
```

---

## Cloud-Specific Notes

### AWS
- Use RDS PostgreSQL 15 (`db.r7g.large` minimum)
- ElastiCache Redis 7 with cluster mode (3 shards)
- ALB Ingress Controller or nginx-ingress
- `externalDatabase.sslMode: require` + RDS CA bundle

### GCP (GKE)
- Cloud SQL for PostgreSQL (db-n1-highmem-2)
- Memorystore Redis (5GB, HA)
- Enable Workload Identity for pod-level IAM

### Azure (AKS)
- Azure Database for PostgreSQL Flexible Server
- Azure Cache for Redis (P1 tier)
- AGIC (Application Gateway Ingress) or nginx-ingress

---

## Post-Install

```bash
# Access Grafana
kubectl port-forward svc/observability-grafana 3000:80 -n monitoring
# Open http://localhost:3000 (admin / configured password)

# Register first mesh node
curl -X POST https://api.x0tta6bl4.io/mesh/nodes \
  -H "Authorization: Bearer <JWT>" \
  -d '{"name":"node-1","region":"eu-west"}'

# View topology
curl https://api.x0tta6bl4.io/mesh/topology \
  -H "Authorization: Bearer <JWT>" | jq .
```
