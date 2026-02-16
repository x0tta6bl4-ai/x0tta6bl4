# x0tta6bl4 Project - Complete Directory Structure

## Root Level Files
- .bumpversion.cfg
- .copilot.yaml
- .coveragerc
- .dockerignore
- .env.development
- .env.example
- .env.production
- .frontmatter_template.yaml
- .gitignore
- .gitlab-ci.yml
- .gitlab-ci.yml.ebpf
- .pre-commit-config.yaml
- ALL_TODOS_PREPARED.md
- AUDIT_DOCUMENTS_INVENTORY.md
- baseline_metrics.json
- CELEBRATION_SUMMARY.md
- CHAOS_ENGINEERING_SPECIFICATION.md
- CHECK_ALL_COMPONENTS.md
- check_all_components.sh
- check_pqc.py
- CHECK_YOURSELF.md
- check-containers.sh
- check-system.sh
- cheklist-90-dney.md
- COMPLETE_PROJECT_SUMMARY.md
- COPY_PASTE_DEPLOY.md
- DECISION_MATRIX_2026.md
- DEMO_READY.md
- deploy.sh
- DEPLOYMENT_CHECKLIST.md
- DEPLOYMENT_COMPLETE_2026_01_12.md
- DEPLOYMENT_COMPLETE_FINAL.md
- DEPLOYMENT_COMPLETE_GUIDE.md
- DEPLOYMENT_COMPLETE_SUMMARY.md
- DEPLOYMENT_COMPLETE.md
- DEPLOYMENT_EXECUTED.md
- DEPLOYMENT_GUIDE_2026_01_12.md
- DEPLOYMENT_GUIDE_PRODUCTION.md
- DEPLOYMENT_NEXT_STEPS.md
- DEPLOYMENT_READINESS_CHECK.md
- DEPLOYMENT_READINESS_CHECKLIST.md
- DEPLOYMENT_READY_FINAL.md
- DEPLOYMENT_READY.md
- DEPLOYMENT_ROADMAP_2026.md
- DEPLOYMENT_RUNBOOK.md
- DEPLOYMENT_START.md
- DEPLOYMENT_SUCCESS.md
- DEPLOYMENT_WEEK1.md
- DOCKER_BUILD_PLAN.md
- EBPF_PHASE2_DAYS1-3_COMPLETE.md
- EXECUTION_SUMMARY.md
- FAILURE_INJECTION_FINAL_REPORT_ALL_FIXED_2026_01_08.md
- FAQ_RESPONSES.md
- FEATURES_COMPLETE.md
- FEDERATED_LEARNING_TESTS_COMPLETE.md
- FEEDBACK_RESPONSE_AND_REORIENTATION_2026_01_07.md
- FILES_CHANGED_TECHNICAL_DEBT_SESSION.md
- FILES_CREATED_2026_01_10.txt
- FILES_INDEX.md
- FINAL_2026_ACHIEVEMENTS.md
- FINAL_AUDIT_SUMMARY_2026_01_10.md
- FINAL_AUDIT_SUMMARY.txt
- FINAL_CHECKLIST.md
- FINAL_CLEANUP_REPORT.md
- FINAL_COMPLETION_REPORT_RU.md
- FINAL_COMPLETION_REPORT.md
- FINAL_COMPLETION_SUMMARY.txt
- FINAL_RUSSIAN_SUMMARY.md
- final-deploy.sh
- fix_server_complete.sh
- fix_vpn_connection_refused.sh
- fix_vpn_geosite_error.sh
- FL_ORCHESTRATOR_SPECIFICATION.md
- FULL_ARCHIVE_LIST.txt
- FULL_DIRECTORY_INDEX.md
- FUTURE_ENHANCEMENTS_COMPLETE.md
- FUTURE_PLANS_QUICK_SUMMARY_RUS.txt
- FUTURE_ROADMAP_2026_RUS.md
- GET_DEMO_URL_NOW.md
- get_demo_url.sh
- GET_LIVE_URL_NOW.md
- GET_NGROK_URL.sh
- get-docker.sh
- GETTING_STARTED_CHECKLIST.md
- GNN_OBSERVE_MODE_PLAN.md
- GO_NO_GO_CRITERIA_2026_01_10.md
- GO_NO_GO_DECISION.md
- pyproject.toml
- pytest.ini
- run_all_tests.sh
- run_demo.py
- run_final_tests.sh
- run_server.sh
- run_tests.sh
- run-fastapi.sh

## Project Directory Structure

### Configuration & Documentation
- **config/** - Configuration files for the project
- **docs/** - Project documentation
- **plans/** - Planning and architecture documents
- **.github/** - GitHub Actions workflows
- **.gitlab-ci/** - GitLab CI/CD configuration

### Source Code
- **src/** - Main application source code
  - **adapters/** - External system adapters
  - **ai/** - AI/ML components (federated learning, neural networks)
  - **cli/** - Command-line interface
  - **consensus/** - Consensus algorithms (Raft)
  - **core/** - Core application logic
  - **data_sync/** - Data synchronization (CRDT)
  - **enterprise/** - Enterprise features (RBAC, multi-tenancy)
  - **federated_learning/** - Federated learning orchestration
  - **ledger/** - Blockchain ledger implementation
  - **ml/** - Machine learning models (LoRA, anomaly detection)
  - **monitoring/** - Prometheus/OpenTelemetry monitoring
  - **network/** - Network components (eBPF, mesh VPN)
  - **quantum/** - Quantum computing integration
  - **rag/** - Retrieval-Augmented Generation
  - **sales/** - Sales and payment integration
  - **security/** - Security modules (PQC, mTLS, SPIFFE)
  - **self_healing/** - MAPE-K self-healing architecture
  - **services/** - Service layer
  - **simulation/** - Digital twin simulation
  - **storage/** - Storage solutions (IPFS, KV stores)

### Web & UI
- **web/** - Web interface and API
- **site/** - Landing pages and marketing
- **templates/** - Email and document templates

### Testing & Validation
- **tests/** - Test suite
- **test-results/** - Test result reports
- **benchmarks/** - Performance benchmarks
- **playwright-report/** - Browser automation reports

### Infrastructure
- **docker/** - Docker container configuration
- **deployment/** - Deployment scripts and Kubernetes config
  - **kubernetes/** - Kubernetes manifests and Helm charts
  - **systemd/** - Systemd service files
- **infra/** - Infrastructure configuration
- **terraform/** - Terraform IaC
- **helm/** - Helm charts
- **prometheus/** - Prometheus monitoring
- **alertmanager/** - Alertmanager configuration

### Data & Storage
- **data/** - Data files
- **db/** - Database management
- **backups/** - Backup files
- **demos/** - Demo data

### Operations
- **monitoring/** - Operation monitoring
- **logs/** - Log files
- **.logs/** - Temporary logs

### Development
- **.vscode/** - VSCode configuration
- **.zenflow/** - Zenflow configuration
- **.zencoder/** - Zencoder configuration

### External
- **external_artifacts/** - External dependencies
- **beta-customers/** - Beta customer files
- **business/** - Business-related documents

### Legacy & Archive
- **ROADMAP_legacy/** - Legacy roadmap documents
- **archive/** - Archived files
- **workspace/** - Workspace files

### Personal & Misc
- **личное/** - Personal files
- **Загрузки/** - Downloads
- **другие проекты/** - Other projects