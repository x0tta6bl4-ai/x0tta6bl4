#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPO="${IMAGE_REPO:-x0tta6bl4/mesh-operator}"
IMAGE_TAG="${IMAGE_TAG:-3.4.0}"
KIND_CLUSTER="${KIND_CLUSTER:-x0tta-dev}"
GOARCH_OVERRIDE="${GOARCH_OVERRIDE:-}"
FORCE_FALLBACK_BUILD="${FORCE_FALLBACK_BUILD:-0}"
FORCE_REAL_BUILD="${FORCE_REAL_BUILD:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REAL_OPERATOR_DIR="$REPO_ROOT/mesh-operator"
REAL_OPERATOR_MAIN="$REAL_OPERATOR_DIR/cmd/manager/main.go"
FALLBACK_SRC="$REPO_ROOT/scripts/ops/mesh_operator_fallback_manager/main.go"
MANAGER_DOCKERFILE="$REPO_ROOT/docker/mesh-operator-fallback/Dockerfile"
IMAGE_REF="${IMAGE_REPO}:${IMAGE_TAG}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

TMP_BUILD_DIR=""
cleanup_tmp() {
  if [[ -n "${TMP_BUILD_DIR:-}" ]] && [[ -d "$TMP_BUILD_DIR" ]]; then
    rm -rf "$TMP_BUILD_DIR"
  fi
}
trap cleanup_tmp EXIT

if ! command -v docker >/dev/null 2>&1; then
  error "docker not found in PATH"
fi
if ! command -v kind >/dev/null 2>&1; then
  error "kind not found in PATH"
fi

if ! docker info >/dev/null 2>&1; then
  error "docker daemon is not available"
fi

have_image_locally() {
  docker image inspect "$IMAGE_REF" >/dev/null 2>&1
}

detect_goarch() {
  if [[ -n "$GOARCH_OVERRIDE" ]]; then
    echo "$GOARCH_OVERRIDE"
    return
  fi
  go env GOARCH
}

build_image_from_manager_binary() {
  local manager_bin="$1"
  [[ -f "$MANAGER_DOCKERFILE" ]] || error "manager Dockerfile not found: $MANAGER_DOCKERFILE"
  [[ -f "$manager_bin" ]] || error "manager binary not found: $manager_bin"

  info "Building operator image $IMAGE_REF"
  docker build \
    -f "$MANAGER_DOCKERFILE" \
    --build-arg MANAGER_BIN="$(basename "$manager_bin")" \
    -t "$IMAGE_REF" \
    "$(dirname "$manager_bin")" >/dev/null
}

build_real_operator_image() {
  [[ -f "$REAL_OPERATOR_MAIN" ]] || return 1
  command -v go >/dev/null 2>&1 || error "go is required to build operator image"

  local goarch
  local go_cache_dir
  local go_mod_cache_dir
  TMP_BUILD_DIR="$(mktemp -d)"
  goarch="$(detect_goarch)"
  go_cache_dir="/tmp/x0tta-go-cache"
  go_mod_cache_dir="/tmp/x0tta-go-mod-cache"
  mkdir -p "$go_cache_dir" "$go_mod_cache_dir"

  info "Building real mesh-operator manager (GOARCH=$goarch)"
  if ! (
    cd "$REAL_OPERATOR_DIR" && \
    GOCACHE="$go_cache_dir" GOMODCACHE="$go_mod_cache_dir" \
      CGO_ENABLED=0 GOOS=linux GOARCH="$goarch" \
      go build -trimpath -ldflags="-s -w" -o "$TMP_BUILD_DIR/manager" ./cmd/manager
  ); then
    warn "Real operator build failed from $REAL_OPERATOR_DIR"
    return 1
  fi

  build_image_from_manager_binary "$TMP_BUILD_DIR/manager"
  return 0
}

build_fallback_image() {
  [[ -f "$FALLBACK_SRC" ]] || error "fallback source not found: $FALLBACK_SRC"
  command -v go >/dev/null 2>&1 || error "go is required to build fallback image"

  local goarch
  local go_cache_dir
  local go_mod_cache_dir
  TMP_BUILD_DIR="$(mktemp -d)"
  goarch="$(detect_goarch)"
  go_cache_dir="/tmp/x0tta-go-cache"
  go_mod_cache_dir="/tmp/x0tta-go-mod-cache"
  mkdir -p "$go_cache_dir" "$go_mod_cache_dir"

  info "Building fallback /manager binary (GOARCH=$goarch)"
  GOCACHE="$go_cache_dir" GOMODCACHE="$go_mod_cache_dir" \
    CGO_ENABLED=0 GOOS=linux GOARCH="$goarch" \
    go build -trimpath -ldflags="-s -w" -o "$TMP_BUILD_DIR/manager" "$FALLBACK_SRC"

  build_image_from_manager_binary "$TMP_BUILD_DIR/manager"
}

ensure_image() {
  if [[ "$FORCE_FALLBACK_BUILD" == "1" ]]; then
    warn "FORCE_FALLBACK_BUILD=1 set. Rebuilding local compatibility image."
    build_fallback_image
    return
  fi

  if [[ "$FORCE_REAL_BUILD" == "1" ]]; then
    info "FORCE_REAL_BUILD=1 set. Rebuilding real mesh-operator image."
    if build_real_operator_image; then
      return
    fi
    error "FORCE_REAL_BUILD=1 requested, but real operator build failed"
  fi

  if have_image_locally; then
    info "Operator image already present locally: $IMAGE_REF"
    return
  fi

  info "Trying to pull operator image: $IMAGE_REF"
  if docker pull "$IMAGE_REF" >/dev/null 2>&1; then
    info "Pulled operator image: $IMAGE_REF"
    return
  fi

  warn "Pull failed for $IMAGE_REF. Trying local real-operator build."
  if build_real_operator_image; then
    info "Built real operator image locally: $IMAGE_REF"
    return
  fi

  warn "Real operator build unavailable. Falling back to compatibility image."
  build_fallback_image
}

load_into_kind() {
  if ! kind get clusters | grep -qx "$KIND_CLUSTER"; then
    warn "kind cluster '$KIND_CLUSTER' not found; skipping image load"
    return
  fi

  info "Loading image into kind/$KIND_CLUSTER: $IMAGE_REF"
  kind load docker-image "$IMAGE_REF" --name "$KIND_CLUSTER" >/dev/null
}

ensure_image
load_into_kind
info "Image ready: $IMAGE_REF"
