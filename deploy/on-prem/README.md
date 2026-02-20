# x0tta6bl4 MaaS On-Prem Deployment Guide

Enterprise-grade self-hosted Control Plane for x0tta6bl4 Mesh-as-a-Service.

## Prerequisites
- Docker & Docker Compose v2+
- 4GB RAM minimum
- (Optional) Domain name with SSL for the dashboard

## Quick Start

1. **Configure Environment**
   Create a `.env` file in this directory:
   ```bash
   OIDC_ISSUER=https://your-auth-provider.com
   OIDC_CLIENT_ID=your-client-id
   MAAS_TOKEN_SECRET=generate-a-strong-random-hex
   ```

2. **Launch Services**
   ```bash
   docker compose up -d
   ```

3. **Verify Deployment**
   - API & Console: `http://localhost:8000`
   - Prometheus: `http://localhost:9090`
   - Vault: `http://localhost:8200`

## Components
- **Control Plane**: The heart of MaaS (FastAPI).
- **PostgreSQL**: Persistent storage for users, meshes, and audit logs.
- **Redis**: Fast caching for telemetry and rate limiting.
- **Vault**: Local PQC key storage and secret management.
- **Prometheus**: Real-time metrics collection from all nodes.

## Security Note
For production on-prem use, ensure:
- Database passwords are changed from defaults.
- Vault is properly initialized and unsealed (non-dev mode).
- OIDC integration is restricted to your organization's domain.
