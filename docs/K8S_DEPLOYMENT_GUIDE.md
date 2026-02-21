# MaaS Kubernetes Deployment Guide

## Overview

This guide covers the deployment of MaaS (Mesh-as-a-Service) to Kubernetes staging and production environments using Helm charts.

## Prerequisites

### Required Tools
- `kubectl` v1.28+
- `helm` v3.12+
- Access to a Kubernetes cluster (v1.27+)

### Required Infrastructure
- Kubernetes cluster with:
  - Ingress controller (nginx recommended)
  - cert-manager for TLS certificates
  - StorageClass for persistent volumes
  - At least 4 CPU cores and 8GB RAM available

## Quick Start

### 1. Deploy to Staging

```bash
# Set required environment variables
export STRIPE_SECRET_KEY="sk_test_xxx"
export STRIPE_WEBHOOK_SECRET="whsec_xxx"

# Run deployment script
./deploy/scripts/deploy-staging.sh
```

### 2. Manual Deployment

```bash
# Create namespace
kubectl create namespace maas-staging

# Add Helm repositories
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Deploy with Helm
helm install maas deploy/helm/maas \
  --namespace maas-staging \
  --values deploy/helm/maas/values-staging.yaml \
  --set stripe.secretKey="sk_test_xxx" \
  --set stripe.webhookSecret="whsec_xxx"
```

## Configuration

### Values Files

| File | Environment | Description |
|------|-------------|-------------|
| `values.yaml` | Default | Base configuration |
| `values-staging.yaml` | Staging | Staging overrides |
| `values-production.yaml` | Production | Production overrides (create as needed) |

### Key Configuration Options

#### API Server

```yaml
api:
  replicaCount: 2
  image:
    repository: maas-x0tta6bl4/api
    tag: "latest"
  resources:
    limits:
      cpu: 1000m
      memory: 1Gi
    requests:
      cpu: 250m
      memory: 512Mi
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
```

#### PostgreSQL

```yaml
postgresql:
  enabled: true
  auth:
    postgresPassword: "change-me"
    username: "maas"
    password: "change-me"
    database: "maas"
  primary:
    persistence:
      enabled: true
      size: 20Gi
```

#### Redis

```yaml
redis:
  enabled: true
  auth:
    enabled: true
    password: "change-me"
  master:
    persistence:
      enabled: true
      size: 5Gi
```

#### Stripe Integration

```yaml
stripe:
  enabled: true
  secretKey: ""  # Set via --set or secrets
  webhookSecret: ""  # Set via --set or secrets
```

### Environment Variables

The following environment variables are automatically configured:

| Variable | Description | Source |
|----------|-------------|--------|
| `DATABASE_URL` | PostgreSQL connection string | Secret |
| `REDIS_URL` | Redis connection string | Secret |
| `STRIPE_SECRET_KEY` | Stripe API key | Secret |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | Secret |
| `ENVIRONMENT` | Environment name | ConfigMap |
| `LOG_LEVEL` | Logging level | ConfigMap |

## Components

### API Server (`maas-api`)

Main REST API server handling:
- Mesh instance management
- Node provisioning
- Billing integration
- Authentication

### Controller (`maas-controller`)

Background controller for:
- Mesh orchestration
- Node health monitoring
- Auto-scaling decisions

### Worker (`maas-worker`)

Celery workers for:
- Background job processing
- Provisioning tasks
- Billing webhooks
- Notifications

### SPIRE/SPIFFE

Identity management for mesh nodes:
- X.509 SVID issuance
- Workload attestation
- Trust bundle distribution

## Monitoring

### Prometheus Metrics

MaaS exposes the following metrics:

```
# Request metrics
maas_requests_total{endpoint, method, status}
maas_request_duration_seconds_bucket{endpoint, le}

# Mesh metrics
maas_mesh_nodes_total
maas_mesh_nodes_active
maas_mesh_traffic_bytes_total{direction}

# Billing metrics
maas_billing_revenue_total
maas_billing_subscriptions_total{status}
maas_billing_webhooks_total{type, status}
```

### Grafana Dashboards

Pre-configured dashboards:
- **MaaS Overview**: High-level metrics and KPIs
- **MaaS Mesh**: Mesh network health and traffic
- **MaaS Billing**: Revenue and subscription metrics

Access Grafana:
```bash
kubectl port-forward svc/maas-grafana 3000:80 -n maas-staging
```

Default credentials: `admin` / `admin` (change in production)

## Scaling

### Horizontal Pod Autoscaler

HPA is enabled by default for API servers:

```yaml
api:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
```

### Manual Scaling

```bash
# Scale API servers
kubectl scale deployment maas-api --replicas=5 -n maas-staging

# Scale workers
kubectl scale deployment maas-worker --replicas=10 -n maas-staging
```

## Upgrades

### Helm Upgrade

```bash
# Dry-run to see changes
helm upgrade maas deploy/helm/maas \
  --namespace maas-staging \
  --values deploy/helm/maas/values-staging.yaml \
  --dry-run

# Apply upgrade
helm upgrade maas deploy/helm/maas \
  --namespace maas-staging \
  --values deploy/helm/maas/values-staging.yaml
```

### Database Migrations

```bash
# Run migrations before upgrading
kubectl exec -it deployment/maas-api -n maas-staging -- alembic upgrade head
```

## Rollback

```bash
# List releases
helm history maas -n maas-staging

# Rollback to previous version
helm rollback maas -n maas-staging

# Rollback to specific revision
helm rollback maas 2 -n maas-staging
```

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n maas-staging
kubectl describe pod maas-api-xxx -n maas-staging
```

### View Logs

```bash
# API logs
kubectl logs -f deployment/maas-api -n maas-staging

# Worker logs
kubectl logs -f deployment/maas-worker -n maas-staging

# All containers
kubectl logs -f -l app.kubernetes.io/name=maas -n maas-staging --all-containers
```

### Check Events

```bash
kubectl get events -n maas-staging --sort-by='.lastTimestamp'
```

### Database Connection

```bash
# Connect to PostgreSQL
kubectl exec -it maas-postgresql-0 -n maas-staging -- psql -U maas -d maas

# Check connections
kubectl exec -it maas-postgresql-0 -n maas-staging -- psql -U maas -d maas -c "SELECT count(*) FROM pg_stat_activity;"
```

### Redis Connection

```bash
# Connect to Redis
kubectl exec -it maas-redis-master-0 -n maas-staging -- redis-cli

# Check connections
kubectl exec -it maas-redis-master-0 -n maas-staging -- redis-cli INFO clients
```

## Security

### Network Policies

Network policies are enabled by default to restrict traffic:

```yaml
networkPolicy:
  enabled: true
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
  egress:
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 5432
        - protocol: TCP
          port: 6379
```

### RBAC

Service account with minimal permissions:

```yaml
rbac:
  create: true
```

### Pod Security

Containers run as non-root with read-only filesystem:

```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000

containerSecurityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
```

## Production Checklist

Before deploying to production:

- [ ] Change all default passwords
- [ ] Configure TLS certificates
- [ ] Enable network policies
- [ ] Set up backup for PostgreSQL
- [ ] Configure alerting rules
- [ ] Review resource limits
- [ ] Enable audit logging
- [ ] Configure external secrets (Vault, AWS Secrets Manager)
- [ ] Set up disaster recovery
- [ ] Configure rate limiting

## Support

For issues and questions:
- GitHub Issues: https://github.com/maas-x0tta6bl4/maas-platform/issues
- Documentation: https://docs.maas-x0tta6bl4.local
