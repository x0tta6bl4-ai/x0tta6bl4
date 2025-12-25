# 🔄 x0tta6bl4 Repository Migration Guide

Status: Draft (P0–P2)
Last Updated: 2025-11-12

## Goals
- Remove repository bloat (venv, databases, archives)
- Establish DVC for datasets/embeddings
- Store vector indexes and artifacts in S3/MinIO
- Enforce hygiene via CI/CD

## New Structure
```
data/
  raw/           # DVC
  processed/     # DVC
  embeddings/    # DVC
  indexes/       # metadata only (indexes in S3)
  private/
  samples/
.cache/
  vector_indexes/
  models/
  temp/
external_artifacts/
  releases/
  snapshots/
  backups/
db/
  migrations/
scripts/
  scan_db_secrets.py
  maintenance/
```

## Quick Start (Dev)
1) Start MinIO locally
```
docker compose -f docker-compose.minio.yml up -d
```
2) Configure DVC (if enabled)
```
dvc init
# Local MinIO remote (example)
dvc remote add -d local s3://dvc-storage
dvc remote modify local endpointurl http://localhost:9000
dvc remote modify local access_key_id x0tta6bl4
dvc remote modify local secret_access_key $MINIO_ROOT_PASSWORD
```
3) Local databases
```
mkdir -p ~/.local/share/x0tta6bl4/databases
export DATABASE_URL="sqlite:///$HOME/.local/share/x0tta6bl4/databases/main.db"
```

## Hygiene Rules (Summary)
- NEVER commit: venv/.venv, *.db, *.sqlite*, archives (*.tar.gz, *.zip, ...), indexes (*.faiss, *.hnsw, *.idx), secrets (.env)
- Datasets: track with DVC (data/raw, data/processed, data/embeddings)
- Indexes: store in S3/MinIO (vector-indexes bucket)
- Artifacts: external_artifacts/ manifests only; binaries go to object storage

## CI/CD
- repo-hygiene: fail on venv, *.db, large files (>10MB)
- dvc-validation: status + dry-run pull
- secrets-scan: detect-secrets
- tests, build, deploy: as configured in .gitlab-ci.yml

## Cleanup Workflow
1) Generate large files report (dry-run)
```
chmod +x scripts/generate_large_files_report.sh
./scripts/generate_large_files_report.sh
```
2) Review and approve removals (git rm --cached, move .db to ~/.local/share/x0tta6bl4/databases)
3) Initialize DVC, add datasets, push to remote
4) Migrate indexes to S3/MinIO

## Troubleshooting
- DVC pull failed: check remote, MinIO health, credentials
- DB not found: ensure DATABASE_URL and directory exist
- CI hygiene fails: remove/relocate flagged files; use DVC or artifact storage

## Roadmap (Prod)
- Cloudflare R2 as primary object storage (zero egress)
- Enforce size gates in CI (<10MB in Git)
- Pre-commit hooks: ruff, mypy, detect-secrets
