#!/usr/bin/env bash
set -euo pipefail

IMAGE_REPO="${IMAGE_REPO:-x0tta6bl4/mesh-node}"
IMAGE_TAG="${IMAGE_TAG:-3.4.0}"
KIND_CLUSTER="${KIND_CLUSTER:-x0tta-dev}"
GOARCH_OVERRIDE="${GOARCH_OVERRIDE:-}"
FORCE_FALLBACK_BUILD="${FORCE_FALLBACK_BUILD:-0}"
FORCE_REAL_BUILD="${FORCE_REAL_BUILD:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

REAL_NODE_DOCKERFILE="$REPO_ROOT/docker/mesh-node/Dockerfile"
FALLBACK_SRC="$REPO_ROOT/scripts/ops/mesh_node_fallback_manager/main.go"
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

build_image_from_binary() {
  local binary_path="$1"
  [[ -f "$binary_path" ]] || error "binary not found: $binary_path"
  [[ -f "$MANAGER_DOCKERFILE" ]] || error "Dockerfile not found: $MANAGER_DOCKERFILE"

  info "Building image $IMAGE_REF from fallback binary"
  docker build \
    -f "$MANAGER_DOCKERFILE" \
    --build-arg MANAGER_BIN="$(basename "$binary_path")" \
    --label "x0tta6bl4.mesh-node.fallback=true" \
    -t "$IMAGE_REF" \
    "$(dirname "$binary_path")" >/dev/null
}

build_real_node_image() {
  [[ -f "$REAL_NODE_DOCKERFILE" ]] || return 1
  info "Building real mesh-node image from docker/mesh-node/Dockerfile"
  docker build -f "$REAL_NODE_DOCKERFILE" -t "$IMAGE_REF" "$REPO_ROOT" >/dev/null
  verify_real_node_runtime
}

build_fallback_node_image() {
  [[ -f "$FALLBACK_SRC" ]] || error "fallback source not found: $FALLBACK_SRC"
  command -v go >/dev/null 2>&1 || error "go is required to build fallback node image"

  local goarch
  local go_cache_dir
  local go_mod_cache_dir
  TMP_BUILD_DIR="$(mktemp -d)"
  goarch="$(detect_goarch)"
  go_cache_dir="/tmp/x0tta-go-cache"
  go_mod_cache_dir="/tmp/x0tta-go-mod-cache"
  mkdir -p "$go_cache_dir" "$go_mod_cache_dir"

  info "Building mesh-node fallback binary (GOARCH=$goarch)"
  GOCACHE="$go_cache_dir" GOMODCACHE="$go_mod_cache_dir" \
    CGO_ENABLED=0 GOOS=linux GOARCH="$goarch" \
    go build -trimpath -ldflags="-s -w" -o "$TMP_BUILD_DIR/manager" "$FALLBACK_SRC"

  build_image_from_binary "$TMP_BUILD_DIR/manager"
}

verify_real_node_runtime() {
  info "Validating real mesh-node runtime imports"
  if docker run --rm --entrypoint python3 "$IMAGE_REF" -c "from libx0t.network.mesh_node import MeshNode, MeshNodeConfig" >/dev/null 2>&1; then
    return 0
  fi
  warn "Runtime validation failed for $IMAGE_REF"
  return 1
}

is_fallback_image_local() {
  local marker
  marker="$(docker image inspect "$IMAGE_REF" --format '{{ index .Config.Labels "x0tta6bl4.mesh-node.fallback" }}' 2>/dev/null || true)"
  [[ "$marker" == "true" ]]
}

ensure_image() {
  if [[ "$FORCE_FALLBACK_BUILD" == "1" ]]; then
    warn "FORCE_FALLBACK_BUILD=1 set. Rebuilding mesh-node fallback image."
    build_fallback_node_image
    return
  fi

  if [[ "$FORCE_REAL_BUILD" == "1" ]]; then
    info "FORCE_REAL_BUILD=1 set. Rebuilding real mesh-node image."
    if build_real_node_image; then
      return
    fi
    error "FORCE_REAL_BUILD=1 requested, but real mesh-node build failed"
  fi

  if have_image_locally; then
    info "Mesh-node image already present locally: $IMAGE_REF"
    if is_fallback_image_local; then
      info "Local mesh-node image is fallback-compatible. Reusing."
      return
    fi
    if verify_real_node_runtime; then
      return
    fi
    warn "Local mesh-node image is not runtime-healthy. Rebuilding."
  fi

  info "Trying to pull mesh-node image: $IMAGE_REF"
  if docker pull "$IMAGE_REF" >/dev/null 2>&1; then
    info "Pulled mesh-node image: $IMAGE_REF"
    if verify_real_node_runtime; then
      return
    fi
    warn "Pulled mesh-node image failed runtime validation."
  fi

  warn "Pull failed for $IMAGE_REF. Trying local real mesh-node build."
  if build_real_node_image; then
    info "Built real mesh-node image locally: $IMAGE_REF"
    return
  fi

  warn "Real mesh-node build unavailable. Falling back to compatibility image."
  build_fallback_node_image
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
