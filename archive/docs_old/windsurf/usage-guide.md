# Using Windsurf with x0tta6bl4

Status: Draft

Quick Commands:
- Generate report: run step `generate-large-files-report` in cleanup-workflow.yaml
- Scan DBs: run step `scan-db-secrets`
- Dry-run cleanup: run step `dry-run-git-clean`

Typical Flow:
1) Generate large files report
2) Review SUMMARY.md
3) Decide per-category actions (venv, db, archives)
4) Run dry-run cleanup
5) Stage removal from Git index (no deletion)
6) Initialize and configure DVC remote (MinIO)
7) dvc add + push datasets

Do/Don’t:
- Do keep binaries out of Git; use DVC/MinIO
- Do relocate local DBs to ~/.local/share/x0tta6bl4/databases
- Don’t commit venvs, archives, model weights, indexes

Troubleshooting:
- If MinIO not reachable, start via docker-compose.minio.yml
- If DVC push fails, verify endpointurl and credentials
- If CI hygiene fails, inspect report and adjust ignores or move data to DVC

References:
- docs/windsurf/project-structure.md
- docs/windsurf/cleanup-workflow.yaml
- README.MIGRATION.md
