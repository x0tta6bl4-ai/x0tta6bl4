# x0tta6bl4 MaaS: Production Deployment Guide
## Version 3.4.0 (Enterprise-Ready)

This guide details the procedure for deploying the complete x0tta6bl4 Mesh-as-a-Service stack in a production environment.

---

### 1. Infrastructure Requirements
- **OS**: Ubuntu 22.04 LTS or Debian 12.
- **Resources**: 
  - API Node: 4 CPU, 8GB RAM, 50GB SSD.
  - Database Node: 2 CPU, 4GB RAM, 100GB SSD (NVMe preferred).
- **Network**: Public IP, Ports 80/443 (Control Plane), 9001 (Mesh), 8200 (Vault).

### 2. Stack Components
- **API**: FastAPI (Modular architecture).
- **Database**: PostgreSQL 15 (SQLAlchemy ORM).
- **Cache/Telemetry**: Redis 7.
- **Secrets**: HashiCorp Vault.
- **Reverse Proxy**: Caddy (Auto-HTTPS).
- **Observability**: Prometheus & Grafana.

---

### 3. Step-by-Step Deployment

#### Step 1: Clone and Prepare Environment
```bash
git clone https://github.com/x0tta6bl4/maas.git
cd x0tta6bl4
cp .env.example .env
```
Edit `.env` with production credentials:
- `DATABASE_URL`: Point to your Postgres instance.
- `REDIS_URL`: Point to your Redis instance.
- `VAULT_TOKEN`: Master token for signing secrets.
- `OIDC_CLIENT_ID`: Your Enterprise SSO ID.

#### Step 2: Secret Management (Vault Setup)
Initialize Vault and store the master signing key:
```bash
vault secrets enable -path=maas kv-v2
vault kv put maas/signing-key secret="YOUR_PQC_BACKED_MASTER_SECRET"
```

#### Step 3: Launch Containers
```bash
docker compose -f docker-compose.prod.yml up -d
```

#### Step 4: Database Migrations
Initialize the production schema:
```bash
docker exec -it maas-api python3 -c "from src.database import create_tables; create_tables()"
```

---

### 4. Zero-Trust Node Enrollment
To join a new physical agent to the production mesh:
1. Generate a Join Token in the Control Plane dashboard.
2. Run the installer on the target node:
   ```bash
   curl -sL https://install.x0tta6bl4.net | bash -s -- --mesh-id mesh-xxxx --token x0t_yyyy
   ```
3. (Optional) If Enterprise, ensure **TPM 2.0** is active for hardware attestation.

### 5. Governance & Autonomous Pricing
The **PricingAgent** runs autonomously within the API. To participate in governance:
1. Log in via OIDC SSO.
2. Navigate to the **DAO** tab.
3. Review active proposals from the AI agent and cast your quadratic vote.

---

### 6. Security Best Practices
- **Isolation**: Keep the Database and Redis in a private VPC.
- **PQC Monitoring**: Check `pqc_handshakes_completed` metric in Prometheus to ensure encryption integrity.
- **Audit Logs**: Regularly export audit logs via `GET /api/v1/maas/{id}/audit-logs/export`.

---
*Enterprise Support: enterprise@x0tta6bl4.net*
