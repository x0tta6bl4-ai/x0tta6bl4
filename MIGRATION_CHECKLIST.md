# Migration Checklist – x0tta6bl4 Restructure

## Phase 1 – Audit & Tag
- [x] Create migration branch: restructure/main-migration-20251104
- [ ] Create safety tag v0.9.5-pre-restructure (retry after initial commit)
- [x] Generate INVENTORY.json
- [ ] Generate DUPLICATION_REPORT.md (infra vs infrastructure vs infrastructure-optimizations)
- [ ] Generate DEPENDENCY_DIFF.md (requirements_* vs consolidated)

## Phase 2 – Cleanup & Archive
- [ ] Create archive/ directory skeleton
- [ ] Move backups (x0tta6bl4_backup_*, previous/, *.tar.gz, *.zip) to archive/
- [ ] Update .gitignore with archive/artifacts/, .venv*/, large assets
- [ ] Remove stray egg-info from version control

## Phase 3 – Code Restructure
- [ ] Create src/ subtrees (core, security, network, ml, monitoring, adapters)
- [ ] Relocate run_api_server.py → src/core/api_server.py
- [ ] Relocate notification-suite.py → src/core/notification_suite.py
- [ ] Move mape-k / drift / auto-recovery modules → src/monitoring/
- [ ] Move rag / lora modules → src/ml/{rag,lora}/
- [ ] Consolidate YAML manifests → infra/k8s/
- [ ] Consolidate Dockerfile variants → infra/docker/
- [ ] Consolidate terraform files → infra/terraform/
- [ ] Isolate quantum / paradox → research/{quantum,experiments/}

## Phase 4 – Documentation & Metadata
- [ ] Inject front-matter into all docs/*.md
- [ ] Create docs/ARCHITECTURE.md (refined overview post-move)
- [ ] Create docs/OPERATIONS.md (MAPE-K + incident response)
- [ ] Create docs/COPILOT_PROMPTS.md
- [ ] Update CHANGELOG.md with restructure section

## Phase 5 – Testing & CI/CD
- [ ] Create tests/ hierarchy (unit, integration, security, performance)
- [ ] Migrate test files into tests/
- [ ] Add coverage configuration (pytest + coverage gate)
- [ ] Add .github/workflows/ci.yml
- [ ] Add security-scan.yml
- [ ] Add benchmarks.yml
- [ ] Add release.yml

## Phase 6 – Copilot & Tooling
- [x] Initial .copilot.yaml created
- [ ] Refine .copilot.yaml with new paths post-move
- [ ] Add .vscode/copilot-context.md
- [ ] Add pre-commit config for black, flake8, bandit, detect-secrets
- [ ] Add prompt cookbook

## Phase 7 – Rollout & Validation
- [ ] Perform staging deploy (dry-run)
- [ ] Run smoke tests (mesh, mTLS, MAPE-K events)
- [ ] Validate SBOM generation & security scans
- [ ] Tag release v0.9.5-restructure
- [ ] Final executive summary update

## Rollback Preparedness
- Safety tag present
- Branch intact
- Inventory saved
- Document MIGRATION_CHECKLIST.md progress

## Notes
- Tag creation failed initially due to no commits on branch yet – perform an initial commit before retry.
- INVENTORY.json size large; consider compressing or sampling for reports.
