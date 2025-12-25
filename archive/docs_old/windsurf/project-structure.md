# Project Structure and Hygiene Rules (Windsurf)

Status: Always On (Advisory)

Goals:
- Keep Git history small and clean.
- Keep virtualenvs, databases, and binary artifacts out of Git.
- Use DVC and object storage (MinIO/R2) for large data.

Key Directories:
- data/raw, data/processed, data/embeddings — tracked with DVC
- data/indexes — metadata only; real indexes go to S3 (vector-indexes bucket)
- .cache/ — ephemeral caches (models, temp, vector_indexes)
- external_artifacts/ — manifests only; binaries stored in object storage
- db/migrations/ — schema and migration scripts only
- scripts/ — maintenance and tooling scripts

Ignore Policy (summary):
- Python venvs: venv, .venv, venv_*
- Databases: *.db, *.sqlite*
- Indexes: *.faiss, *.hnsw, *.idx, *.ann, *.nmslib
- Archives: *.tar, *.tar.gz, *.tgz, *.zip, *.7z, *.rar
- Pickle/npz: *.pkl, *.joblib, *.npz
- Secrets: .env, *.key, id_*
- IDE: .vscode/, .idea/
- DVC: actual data files via .dvc tracking, not Git

Data Flows:
- Datasets: add via `dvc add`, push to MinIO remote
- Indexes: write/read from S3-compatible store, not Git
- DBs: local at ~/.local/share/x0tta6bl4/databases; configure via DATABASE_URL

Security:
- Scan SQLite with scripts/scan_db_secrets.py before moving
- Use detect-secrets or similar scanning in CI

CI Expectations:
- Fail on large binaries in Git (>10MB) unless justified
- Verify DVC remotes and metadata consistency

Operations Checklist:
- Large file report before cleanup
- Approve removal from index (git rm --cached) after review
- Move DBs to local storage, datasets to DVC remote

References:
- README.MIGRATION.md
- .gitignore (strengthened)
- docker-compose.minio.yml
