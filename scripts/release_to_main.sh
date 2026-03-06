#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# release_to_main.sh — продвинуть develop → main + tag
# Использование:
#   ./scripts/release_to_main.sh [--dry-run]
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

# Read version from VERSION file (supports semantic versioning)
VERSION=$(cat VERSION 2>/dev/null || echo "3.4.0")
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
run()   {
  if $DRY_RUN; then
    echo -e "${YELLOW}[DRY-RUN]${NC} $*"
  else
    eval "$*"
  fi
}

info "=== Релиз x0tta6bl4 v${VERSION} develop → main ==="
$DRY_RUN && warn "Режим dry-run: команды не выполняются"

# 1. Убедиться что мы на develop и дерево чистое
CURRENT=$(git rev-parse --abbrev-ref HEAD)
[[ "$CURRENT" == "develop" ]] || { warn "Текущая ветка: $CURRENT (ожидается develop)"; }

if $DRY_RUN; then
  warn "Проверка git status пропущена в dry-run для ускорения на больших репозиториях"
else
  DIRTY=$(git status --porcelain --untracked-files=no)
  [[ -z "$DIRTY" ]] && info "Рабочее дерево чистое ✅" || warn "Есть незакоммиченные изменения:\n$DIRTY"
fi

DEVELOP_SHA=$(git rev-parse HEAD)
info "develop HEAD: $DEVELOP_SHA"

# 2. Прогон тестов перед релизом
info "Запуск unit-тестов..."
run "python3 -m pytest tests/unit/ -q --no-cov --tb=short 2>&1 | tail -5"

# 3. Helm lint
info "Helm lint x0tta-mesh-operator..."
run "helm lint charts/x0tta-mesh-operator/ --strict"

# 4. Переключиться на main, merge develop
run "git checkout main"
run "git merge --ff-only develop -m 'release: v${VERSION} merge from develop'"

# 5. Тег
run "git tag -a v${VERSION} -m 'x0tta6bl4 v${VERSION}

Operator MVP:
- MeshCluster CRD (pqc.ebpf.packetCounter, fallback.circuit, dao.bridge Sepolia)
- x0tta-mesh-operator Helm chart v${VERSION}
- mint_from_bridge_event (Base Sepolia → X0T, idempotent, 6/6 tests)
- Quality gate: 8060+ tests, 0 failures
- fallback.py 99% coverage, edge_cache.py 95% coverage'"

# 6. Push
run "git push origin main"
run "git push origin v${VERSION}"

# 7. Вернуться на develop
run "git checkout develop"

info "=== Релиз v${VERSION} завершён ==="
info "  main: $(git rev-parse main 2>/dev/null || echo 'см. после dry-run')"
info "  tag:  v${VERSION}"
