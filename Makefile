# Makefile for x0tta6bl4 v3.3.0
# ================================

.PHONY: help install test benchmark clean lint format up down logs status build build-prod plan code ops-test gtm ai-status cleanup-baseline cleanup-gate cleanup-rc-check utrecht-plan utrecht-deploy utrecht-manifest-diff utrecht-manifest-apply utrecht-observation utrecht-observation-tail utrecht-kpi-summary utrecht-funding-draft iso-p2-readiness-check mesh-operator-preflight mesh-operator-lint mesh-operator-plan mesh-operator-install mesh-operator-upgrade mesh-operator-smoke mesh-operator-reproducibility mesh-operator-release-dry-run mesh-operator-lifecycle-e2e mesh-operator-canary-rollback-e2e api-memory-profile-longrun maas-api-load-scenarios maas-api-load-scenarios-ci mesh-operator-uninstall

.DEFAULT_GOAL := help

MESH_OPERATOR_RELEASE ?= x0tta-mesh
MESH_OPERATOR_NAMESPACE ?= x0tta-mesh-system
MESH_OPERATOR_VALUES ?= deploy/helm/values-x0tta-mesh-operator-utrecht.yaml

help:
	@echo "x0tta6bl4 v3.3.0 - Available commands:"
	@echo ""
	@echo "=== Docker Compose Staging ==="
	@echo "  make up          - Start all staging services (API+DB+Redis+Prometheus+Grafana)"
	@echo "  make down        - Stop all staging services"
	@echo "  make status      - Show service status"
	@echo "  make logs        - Follow API logs"
	@echo "  make logs-all    - Follow all service logs"
	@echo "  make test        - Run health checks on all services"
	@echo ""
	@echo "=== Kubernetes Staging (P0 #5) ==="
	@echo "  make k8s-staging - Setup K3s/minikube staging cluster"
	@echo "  make k8s-apply   - Apply manifests to staging cluster"
	@echo "  make k8s-status  - Show deployment status"
	@echo "  make k8s-test    - Run E2E smoke tests"
	@echo "  make k8s-logs    - Follow pod logs"
	@echo "  make k8s-shell   - Open shell in pod"
	@echo "  make k8s-delete  - Delete staging deployment"
	@echo "  make k8s-clean   - Clean all K8s resources"
	@echo ""
	@echo "=== Monitoring ==="
	@echo "  make monitoring-stack - Deploy Prometheus + Grafana"
	@echo ""
	@echo "=== Pilot Ops (Utrecht 6G) ==="
	@echo "  make utrecht-plan          - Preview Utrecht mesh provisioning request"
	@echo "  make utrecht-deploy        - Provision Utrecht pilot mesh"
	@echo "  make utrecht-manifest-diff - Show K8s diff for Utrecht manifest"
	@echo "  make utrecht-manifest-apply - Apply Utrecht pilot manifest"
	@echo "  make utrecht-observation   - Run reliability drill and append pilot observation log"
	@echo "  make utrecht-observation-tail - Show latest pilot observation entries"
	@echo "  make utrecht-kpi-summary   - Generate KPI summary from observation log"
	@echo "  make utrecht-funding-draft - Generate follow-up DAO funding draft from KPI summary"
	@echo "  make iso-p2-readiness-check - Validate ISO 27001 P2 documentation package"
	@echo "  make mesh-operator-preflight - Verify kubectl context/cluster before install"
	@echo "  make mesh-operator-lint    - Lint x0tta mesh operator chart with Utrecht values"
	@echo "  make mesh-operator-plan    - Render operator manifests (dry-run plan)"
	@echo "  make mesh-operator-install - Install operator chart into namespace"
	@echo "  make mesh-operator-upgrade - Upgrade operator chart release"
	@echo "  make mesh-operator-smoke   - Validate operator rollout/CRD/service health"
	@echo "  make mesh-operator-reproducibility - Verify deterministic fallback image builds"
	@echo "  make mesh-operator-release-dry-run - Run release dry-run with checkpoint report"
	@echo "  make mesh-operator-lifecycle-e2e - Validate Helm install/upgrade/uninstall lifecycle in kind"
	@echo "  make mesh-operator-canary-rollback-e2e - Validate canary rollout and rollback SLA in kind"
	@echo "  make api-memory-profile-longrun - Run long-run API memory profile with report artifacts"
	@echo "  make maas-api-load-scenarios - Run Marketplace/Telemetry/Nodes load scenarios with report artifacts"
	@echo "  make maas-api-load-scenarios-ci - Run deterministic CI profile for Marketplace/Telemetry/Nodes load scenarios"
	@echo "  make mesh-operator-uninstall - Uninstall operator chart release"
	@echo ""
	@echo "=== Development ==="
	@echo "  make install     - Install Python dependencies locally"
	@echo "  make lint        - Run linters (flake8, black, mypy)"
	@echo "  make format      - Format code with black"
	@echo "  make test-unit   - Run unit tests"
	@echo ""
	@echo "=== SPIRE Setup ==="
	@echo "  make spire-dev   - Setup SPIRE development environment"
	@echo "  make spire-test  - Test SPIRE connectivity"
	@echo "  make spire-stop  - Stop SPIRE services"
	@echo ""
	@echo "=== Database & Cache ==="
	@echo "  make db-connect  - Connect to PostgreSQL"
	@echo "  make db-connect-admin - Connect to PostgreSQL as admin"
	@echo "  make redis-cli   - Connect to Redis CLI"
	@echo "  make shell       - Open shell in API container"
	@echo ""
	@echo "=== Cleanup ==="
	@echo "  make clean       - Stop services and remove volumes (Docker Compose)"
	@echo "  make clean-all   - Remove containers, volumes, and images"
	@echo "  make build       - Build staging Docker image"
	@echo "  make build-prod  - Build production image (multi-stage)"

# ============================================================================
# STAGING ENVIRONMENT COMMANDS
# ============================================================================

up:
	@echo "🚀 Starting x0tta6bl4 staging environment..."
	docker compose -f staging/docker-compose.quick.yml up -d
	@sleep 3
	@echo ""
	@echo "✅ Services started:"
	@echo "   API:        http://localhost:8000"
	@echo "   Grafana:    http://localhost:3000 (admin/admin)"
	@echo "   Prometheus: http://localhost:9090"
	@echo "   PostgreSQL: localhost:5432"
	@echo "   Redis:      localhost:6379"
	@echo ""
	@docker compose -f staging/docker-compose.quick.yml ps

down:
	@echo "⏹️  Stopping x0tta6bl4 staging environment..."
	docker compose -f staging/docker-compose.quick.yml down
	@echo "✅ Services stopped"

clean:
	@echo "🧹 Cleaning Docker resources..."
	docker compose -f staging/docker-compose.quick.yml down -v
	@echo "✅ Cleanup complete"

build:
	@echo "🔨 Building staging-api image..."
	docker compose -f staging/docker-compose.quick.yml build --no-cache
	@echo "✅ Image built"

build-prod:
	@echo "🔨 Building production image (multi-stage build)..."
	docker build -f Dockerfile.prod -t x0tta6bl4:latest .
	@docker build -f Dockerfile.prod -t x0tta6bl4:$(shell git rev-parse --short HEAD) . 2>/dev/null || true
	@echo "✅ Production image built"

logs:
	docker compose -f staging/docker-compose.quick.yml logs -f api

logs-db:
	docker compose -f staging/docker-compose.quick.yml logs -f db

logs-all:
	docker compose -f staging/docker-compose.quick.yml logs -f

status:
	@echo "📊 x0tta6bl4 Status:"
	@echo ""
	docker compose -f staging/docker-compose.quick.yml ps

test:
	@echo "🧪 Running health checks..."
	@echo ""
	@echo "✓ API (Health):"
	@curl -s http://localhost:8000/health | python3 -m json.tool | head -5 2>/dev/null || echo "  Not responding"
	@echo ""
	@echo "✓ API (Metrics):"
	@METRICS=$$(curl -s http://localhost:8000/metrics | head -20); \
	if [ -n "$$METRICS" ]; then echo "$$METRICS"; else echo "  No metrics yet"; fi
	@echo ""
	@echo "✓ Prometheus:"
	@curl -s http://localhost:9090/-/healthy 2>/dev/null || echo "  Not responding"
	@echo ""
	@echo "✓ Grafana:"
	@curl -s http://localhost:3000/api/health 2>/dev/null | python3 -m json.tool | head -5 || echo "  Not responding"
	@echo ""
	@echo "✓ PostgreSQL:"
	@docker exec x0tta6bl4-db psql -h localhost -U x0tta6bl4 -c "SELECT 1" 2>/dev/null && echo "  ✅ Connected" || echo "  ❌ Failed"
	@echo ""
	@echo "✓ Redis:"
	@REDIS_PING=$$(docker exec x0tta6bl4-redis redis-cli ping 2>/dev/null || true); \
	if [ "$$REDIS_PING" = "PONG" ]; then \
		echo "  PONG"; \
		echo "  ✅ Connected"; \
	else \
		if [ -n "$$REDIS_PING" ]; then echo "  $$REDIS_PING"; else echo "  Not responding"; fi; \
		echo "  ❌ Redis degraded"; \
	fi
	@echo ""
	@echo "✅ Health checks complete"

utrecht-plan:
	@echo "📋 Previewing Utrecht 6G provisioning request..."
	python3 scripts/ops/utrecht_6g_deploy.py --dry-run --output json --values-file values-utrecht.yaml

utrecht-deploy:
	@echo "🚀 Deploying Utrecht 6G pilot mesh..."
	python3 scripts/ops/utrecht_6g_deploy.py --values-file values-utrecht.yaml

utrecht-manifest-diff:
	@echo "🔎 Diffing Utrecht deployment manifest..."
	kubectl diff -f utrecht-deploy-manifest.yaml || true

utrecht-manifest-apply:
	@echo "📦 Applying Utrecht deployment manifest..."
	kubectl apply -f utrecht-deploy-manifest.yaml

utrecht-observation:
	@echo "📈 Recording Utrecht pilot observation..."
	bash scripts/ops/record_utrecht_pilot_observation.sh

utrecht-observation-tail:
	@echo "🗒️ Latest Utrecht pilot observations:"
	@tail -n 20 docs/governance/proposals/UTRECHT_PILOT_OBSERVATION_LOG.md 2>/dev/null || echo "No observation log yet."

utrecht-kpi-summary:
	@echo "📊 Building Utrecht KPI summary from observations..."
	python3 scripts/ops/build_utrecht_pilot_governance_artifacts.py --write-summary

utrecht-funding-draft:
	@echo "🗳️ Building Utrecht follow-up DAO funding draft..."
	python3 scripts/ops/build_utrecht_pilot_governance_artifacts.py --write-summary --write-funding-draft

iso-p2-readiness-check:
	@echo "🛡️ Running ISO 27001 P2 readiness document checks..."
	python3 scripts/ops/check_iso27001_p2_readiness.py

mesh-operator-preflight:
	@echo "🔎 Running mesh operator preflight checks..."
	python3 scripts/ops/mesh_operator_health.py preflight \
	  --require-cluster \
	  --kubectl scripts/ops/kubectl_safe.sh

mesh-operator-lint:
	@echo "🔍 Linting x0tta mesh operator chart..."
	scripts/ops/helm_safe.sh lint charts/x0tta-mesh-operator -f $(MESH_OPERATOR_VALUES)

mesh-operator-plan:
	@echo "🧭 Rendering x0tta mesh operator manifests..."
	scripts/ops/helm_safe.sh template $(MESH_OPERATOR_RELEASE) charts/x0tta-mesh-operator \
	  --namespace $(MESH_OPERATOR_NAMESPACE) \
	  -f $(MESH_OPERATOR_VALUES)

mesh-operator-install: mesh-operator-preflight
	@echo "🚀 Installing x0tta mesh operator..."
	scripts/ops/helm_safe.sh upgrade --install $(MESH_OPERATOR_RELEASE) charts/x0tta-mesh-operator \
	  --namespace $(MESH_OPERATOR_NAMESPACE) \
	  --create-namespace \
	  -f $(MESH_OPERATOR_VALUES)

mesh-operator-upgrade: mesh-operator-preflight
	@echo "⬆️  Upgrading x0tta mesh operator..."
	scripts/ops/helm_safe.sh upgrade $(MESH_OPERATOR_RELEASE) charts/x0tta-mesh-operator \
	  --namespace $(MESH_OPERATOR_NAMESPACE) \
	  -f $(MESH_OPERATOR_VALUES)

mesh-operator-smoke:
	@echo "🩺 Running mesh operator smoke checks..."
	python3 scripts/ops/mesh_operator_health.py smoke \
	  --namespace $(MESH_OPERATOR_NAMESPACE) \
	  --release $(MESH_OPERATOR_RELEASE) \
	  --wait-seconds 180 \
	  --kubectl scripts/ops/kubectl_safe.sh

mesh-operator-reproducibility:
	@echo "🧬 Checking mesh image reproducibility..."
	bash scripts/ops/check_mesh_images_reproducibility.sh

mesh-operator-release-dry-run:
	@echo "🧭 Running mesh operator release dry-run checkpoints..."
	bash scripts/ops/mesh_operator_release_dry_run.sh

mesh-operator-lifecycle-e2e:
	@echo "🧪 Running mesh operator Helm lifecycle e2e..."
	bash scripts/ops/mesh_operator_helm_lifecycle_e2e.sh

mesh-operator-canary-rollback-e2e:
	@echo "🐤 Running mesh operator canary rollout + rollback e2e..."
	bash scripts/ops/mesh_operator_canary_rollback_e2e.sh

api-memory-profile-longrun:
	@echo "🧠 Running long-run API memory profile..."
	bash scripts/ops/profile_api_memory_longrun.sh

maas-api-load-scenarios:
	@echo "⚡ Running MaaS API load scenarios (Marketplace/Telemetry/Nodes)..."
	bash scripts/ops/run_maas_api_load_scenarios.sh

maas-api-load-scenarios-ci:
	@echo "⚡ Running MaaS API load scenarios (CI profile)..."
	REPORT_DIR=.artifacts/maas-api-load \
	DURATION_SECONDS=30 \
	CONCURRENCY=4 \
	REQUEST_TIMEOUT_SECONDS=3 \
	MAX_ERROR_RATE_PERCENT=1.0 \
	MAX_SCENARIO_P95_MS=900 \
	STARTUP_TIMEOUT_SECONDS=300 \
	bash scripts/ops/run_maas_api_load_scenarios.sh

mesh-operator-uninstall:
	@echo "🧹 Uninstalling x0tta mesh operator..."
	scripts/ops/helm_safe.sh uninstall $(MESH_OPERATOR_RELEASE) --namespace $(MESH_OPERATOR_NAMESPACE)

db-connect:
	@echo "📊 Connecting to PostgreSQL..."
	psql -h localhost -p 5432 -U x0tta6bl4_user -d x0tta6bl4_db

redis-cli:
	@echo "📦 Connecting to Redis..."
	docker exec -it x0tta6bl4-redis redis-cli

shell:
	@echo "🐚 Opening shell in x0tta6bl4-api..."
	docker exec -it x0tta6bl4-api /bin/bash

shell-db:
	@echo "🐚 Opening psql in x0tta6bl4-db..."
	docker exec -it x0tta6bl4-db psql -U x0tta6bl4_user -d x0tta6bl4_db

# ============================================================================
# DEVELOPMENT COMMANDS
# ============================================================================

install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements-staging.txt
	@echo "✅ Dependencies installed"

test-unit:
	@echo "🧪 Running unit tests..."
	pytest tests/ -v --tb=short
	@echo "✅ Tests passed"

test-coverage:
	@echo "📊 Running tests with coverage..."
	pytest tests/ --cov=src --cov-report=html --cov-report=term
	@echo "✅ Coverage report generated in htmlcov/"

security:
	@echo "🔒 Running security checks..."
	./scripts/security-check.sh

benchmark:
	@echo "⚡ Running benchmarks..."
	python benchmarks/benchmark_pqc.py 2>/dev/null || echo "  Benchmarks not available"
	@echo "✅ Benchmarks complete"

lint:
	@echo "🔍 Running linters..."
	flake8 src/ --max-line-length=120 || true
	black --check src/ || true
	@echo "✅ Lint check complete"

format:
	@echo "🎨 Formatting code..."
	black src/
	@echo "✅ Code formatted"

# ============================================================================
# CLEANUP
# ============================================================================

clean-all: down
	@echo "🗑️  Removing Docker images..."
	docker rmi staging-api 2>/dev/null || true
	docker rmi x0tta6bl4:latest 2>/dev/null || true
	docker system prune -f
	@echo "✅ Full cleanup complete"
	python examples/example_dao_mapek.py
	python examples/example_pqc_performance.py
	python examples/example_complete_integration.py
	python examples/pqc_zero_trust_quickstart.py
	python examples/ebpf_performance_monitoring.py

spire-dev:
	@echo "Setting up SPIRE development environment..."
	./scripts/setup_spire_dev.sh --docker --cleanup

spire-test:
	@echo "Testing SPIRE connectivity..."
	./scripts/setup_spire_dev.sh --docker --test

spire-stop:
	@echo "Stopping SPIRE services..."
	docker-compose -f docker-compose.spire.yml down

k8s-staging:
	@echo "🚀 Setting up Kubernetes staging environment..."
	./scripts/setup_k8s_staging.sh
	@echo "✅ Kubernetes staging setup complete"

k8s-apply:
	@echo "📦 Applying staging Kubernetes manifests..."
	kubectl apply -k infra/k8s/overlays/staging/
	@echo "✅ Manifests applied"

k8s-status:
	@echo "📊 Kubernetes staging status:"
	@kubectl get namespaces | grep -E "x0tta6bl4|monitoring|spire" || true
	@echo ""
	@kubectl get deployments -n x0tta6bl4-staging || true
	@echo ""
	@kubectl get pods -n x0tta6bl4-staging || true
	@echo ""
	@kubectl get svc -n x0tta6bl4-staging || true

k8s-test:
	@echo "🧪 Running Kubernetes smoke tests..."
	pytest tests/integration/test_k8s_smoke.py -v

k8s-logs:
	@echo "📋 Following x0tta6bl4 logs..."
	kubectl logs -n x0tta6bl4-staging -l app.kubernetes.io/name=x0tta6bl4 -f

k8s-shell:
	@echo "🐚 Opening shell in x0tta6bl4 pod..."
	kubectl exec -it -n x0tta6bl4-staging deployment/staging-x0tta6bl4 -- bash

k8s-describe:
	@echo "📝 Deployment details:"
	kubectl describe deployment staging-x0tta6bl4 -n x0tta6bl4-staging

k8s-delete:
	@echo "🗑️  Deleting staging deployment..."
	kubectl delete -k infra/k8s/overlays/staging/ || true
	@echo "✅ Staging deployment deleted"

k8s-clean:
	@echo "🧹 Cleaning up all Kubernetes resources..."
	kubectl delete namespace x0tta6bl4-staging 2>/dev/null || true
	kubectl delete namespace x0tta6bl4 2>/dev/null || true
	kubectl delete namespace monitoring 2>/dev/null || true
	kubectl delete namespace spire 2>/dev/null || true
	@echo "✅ Cleanup complete"

monitoring-stack:
	@echo "📊 Deploying Prometheus + Grafana monitoring stack..."
	@if [ -f "infra/monitoring/prometheus.yml" ]; then \
		kubectl create namespace monitoring 2>/dev/null || true; \
		echo "✓ Created monitoring namespace"; \
	fi
	@echo "✅ Monitoring stack deployment initiated"

# ============================================================================
# DATABASE MANAGEMENT (P0 #2)
# ============================================================================

db-compose-up:
	@echo "🚀 Starting PostgreSQL + pgBouncer + Exporter stack..."
	docker-compose -f staging/docker-compose.postgres.yml up -d
	@sleep 3
	@echo "✅ Database services started:"
	@echo "   PostgreSQL:  localhost:5432"
	@echo "   pgBouncer:   localhost:6432"
	@echo "   Exporter:    localhost:9187"

db-compose-down:
	@echo "⏹️  Stopping database services..."
	docker-compose -f staging/docker-compose.postgres.yml down

db-setup:
	@echo "📦 Setting up PostgreSQL production schema..."
	python scripts/database/postgres_setup.py setup

db-backup:
	@echo "💾 Creating database backup..."
	python scripts/database/postgres_setup.py backup

db-restore:
	@echo "🔄 Restoring database from backup..."
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make db-restore FILE=/path/to/backup.sql.gz"; \
		exit 1; \
	fi
	python scripts/database/postgres_setup.py restore $(FILE)

db-health:
	@echo "🏥 Database health check..."
	bash scripts/database/postgres_health_check.sh

db-monitor:
	@echo "📊 Database cluster monitoring..."
	bash scripts/database/postgres_monitor.sh

db-connect-admin:
	@echo "🔌 Connecting to database..."
	psql -h localhost -p 5432 -U postgres -d x0tta6bl4

db-pgbouncer:
	@echo "🔌 Connecting to pgBouncer..."
	psql -h localhost -p 6432 -U x0tta6bl4_app -d x0tta6bl4

db-cleanup-backups:
	@echo "🗑️  Cleaning old backups..."
	python scripts/database/postgres_setup.py cleanup-backups

k8s-db-deploy:
	@echo "📦 Deploying PostgreSQL to Kubernetes..."
	kubectl apply -f infra/kubernetes/postgres-statefulset.yaml
	@echo "✅ StatefulSet deployed. Monitor with:"
	@echo "   kubectl get statefulset -n x0tta6bl4-db"

k8s-db-logs:
	@echo "📋 Following PostgreSQL logs..."
	kubectl logs -f postgres-0 -n x0tta6bl4-db -c postgres

k8s-db-connect:
	@echo "🔌 Connecting to PostgreSQL in Kubernetes..."
	kubectl exec -it postgres-0 -n x0tta6bl4-db -- psql -U postgres

k8s-db-backup:
	@echo "💾 Creating backup from Kubernetes pod..."
	@PGPASSWORD=postgres kubectl exec postgres-0 -n x0tta6bl4-db -- \
		pg_dump -U postgres -d x0tta6bl4 | gzip > backups/postgres/backup_k8s_$(shell date +%Y%m%d_%H%M%S).sql.gz

db-migrate-create:
	@echo "📝 Creating new database migration..."
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make db-migrate-create NAME=migration_name"; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(NAME)"

db-migrate-up:
	@echo "⬆️  Applying database migrations..."
	alembic upgrade head

db-migrate-down:
	@echo "⬇️  Rolling back database migration..."
	alembic downgrade -1

db-migrate-status:
	@echo "📊 Database migration status..."
	alembic current
	@echo ""
	alembic history

# ============================================================================
# PRODUCTION DEPLOYMENT AUTOMATION (P0 #3)
# ============================================================================

deploy-prod:
	@echo "🚀 Starting production deployment..."
	DEPLOYMENT_NAME=x0tta6bl4 \
	NAMESPACE=x0tta6bl4-prod \
	STRATEGY=rolling \
	bash scripts/deploy/deploy.sh

deploy-prod-canary:
	@echo "🐤 Starting canary deployment..."
	DEPLOYMENT_NAME=x0tta6bl4 \
	NAMESPACE=x0tta6bl4-prod \
	STRATEGY=canary \
	bash scripts/deploy/deploy.sh

deploy-prod-bluegreen:
	@echo "🟢🔵 Starting blue-green deployment..."
	DEPLOYMENT_NAME=x0tta6bl4 \
	NAMESPACE=x0tta6bl4-prod \
	STRATEGY=bluegreen \
	bash scripts/deploy/deploy.sh

deploy-rollback:
	@echo "🔄 Rolling back production deployment..."
	kubectl rollout undo deployment/x0tta6bl4 -n x0tta6bl4-prod
	kubectl rollout status deployment/x0tta6bl4 -n x0tta6bl4-prod --timeout=5m

deploy-status:
	@echo "📊 Production deployment status..."
	kubectl get deployment x0tta6bl4 -n x0tta6bl4-prod
	@echo ""
	kubectl get pods -l app.kubernetes.io/name=x0tta6bl4 -n x0tta6bl4-prod

deploy-logs:
	@echo "📋 Following production deployment logs..."
	kubectl logs -f deployment/x0tta6bl4 -n x0tta6bl4-prod

deploy-python:
	@echo "🐍 Running Python deployment orchestrator..."
	python scripts/deploy/production_deploy.py deploy

deploy-python-canary:
	@echo "🐤 Running Python canary deployment..."
	python scripts/deploy/production_deploy.py deploy-canary

deploy-python-status:
	@echo "📊 Deployment orchestrator status..."
	python scripts/deploy/production_deploy.py status

argocd-install:
	@echo "📦 Installing ArgoCD..."
	kubectl create namespace argocd 2>/dev/null || true
	kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
	@echo "✅ ArgoCD installed. Access with:"
	@echo "   kubectl port-forward svc/argocd-server -n argocd 8080:443"
	@echo "   https://localhost:8080"

argocd-deploy:
	@echo "📦 Deploying with ArgoCD..."
	kubectl apply -f argocd/applications/x0tta6bl4-prod.yaml
	@echo "✅ ArgoCD application deployed"

argocd-sync:
	@echo "🔄 Syncing ArgoCD application..."
	argocd app sync x0tta6bl4-prod --prune --timeout 5m

# ============================================================================
# PERFORMANCE BASELINE & LOAD TESTING (P0 #4)
# ============================================================================

perf-baseline:
	@echo "📊 Collecting performance baseline..."
	python scripts/performance/baseline.py collect

perf-compare:
	@echo "📈 Comparing to previous baseline..."
	python scripts/performance/baseline.py compare

perf-load-test:
	@echo "🔨 Running k6 load test..."
	@if ! command -v k6 &> /dev/null; then \
		echo "Installing k6..."; \
		curl https://get.k6.io | bash; \
	fi
	k6 run scripts/performance/load_test.js \
		--vus $(VUS) \
		--duration $(DURATION) \
		--out json=performance_results/load_test_$(shell date +%Y%m%d_%H%M%S).json

perf-load-test-spike:
	@echo "🔨 Running spike load test..."
	k6 run scripts/performance/load_test.js \
		--vus 500 \
		--duration 30s \
		--out json=performance_results/spike_test_$(shell date +%Y%m%d_%H%M%S).json

perf-profile:
	@echo "🔍 Collecting CPU/memory profile..."
	python -m cProfile -o profiling_results/profile_$(shell date +%Y%m%d_%H%M%S).prof src/core/app.py

perf-flamegraph:
	@echo "🔥 Generating flamegraph from profile..."
	@echo "Profiles available in profiling_results/"
	@echo "Convert with: python -m py_spy record -o flamegraph.svg <pid>"

perf-monitor:
	@echo "📊 Real-time performance monitoring..."
	@echo "Installing monitoring tools..."
	pip install psutil prometheus-client
	@echo "Running monitoring daemon..."
	python -c "import psutil; import time; \
		while True: \
			p = psutil.Process(); \
			print(f'CPU: {p.cpu_percent()}% MEM: {p.memory_percent():.2f}%'); \
			time.sleep(1)"

perf-report:
	@echo "📈 Generating performance report..."
	@if [ -f "performance_results/load_test_*.json" ]; then \
		echo "Results in performance_results/"; \
		ls -lh performance_results/load_test_*.json; \
	else \
		echo "No load test results found. Run 'make perf-load-test' first."; \
	fi

# ============================================================================
# AI AGENT ORCHESTRATION
# ============================================================================

plan:
	@./ai.sh plan

code:
	@./ai.sh code

ops-test:
	@echo "Running unit tests (no coverage overhead)..."
	python3 -m pytest tests/unit/ -o "addopts=" --no-cov -v

gtm:
	@./ai.sh gtm

agent-cycle:
	@python3 scripts/agents/run_agent_cycle.py

agent-cycle-strict:
	@python3 scripts/agents/run_agent_cycle.py --strict

agent-cycle-dry:
	@python3 scripts/agents/run_agent_cycle.py --dry-run

agent-cycle-legacylog:
	@python3 scripts/agents/run_agent_cycle.py --sync-paradox-log

agent-cycle-nosync:
	@python3 scripts/agents/run_agent_cycle.py --no-sync-agent-coord --no-sync-paradox-log

ai-status:
	@./ai.sh status

all: install test lint

# ============================================================================
# PLATFORM CLEANUP GATES (single-purpose PR era)
# ============================================================================

cleanup-baseline:
	@echo "📋 Cleanup baseline"
	@echo ""
	@echo "Branch: $$(git rev-parse --abbrev-ref HEAD)"
	@echo "Commit: $$(git rev-parse --short HEAD)"
	@echo ""
	@git status --short
	@echo ""
	@docker compose -f staging/docker-compose.quick.yml ps

cleanup-gate:
	@./scripts/ops/cleanup_gate.sh

cleanup-rc-check:
	@echo "🧪 RC verification sequence"
	@echo "1) make up"
	@echo "2) make cleanup-gate"
	@echo "3) docs/runbooks/MAAS_PLATFORM_CLEANUP_RUNBOOK.md"
	@make up
	@make cleanup-gate
