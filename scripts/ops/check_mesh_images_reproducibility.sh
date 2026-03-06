#!/usr/bin/env bash
set -euo pipefail

GOARCH_OVERRIDE="${GOARCH_OVERRIDE:-amd64}"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1704067200}" # 2024-01-01T00:00:00Z
IMAGE_PREFIX="${IMAGE_PREFIX:-x0tta-repro-check}"
KEEP_IMAGES="${KEEP_IMAGES:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FALLBACK_DOCKERFILE="$REPO_ROOT/docker/mesh-operator-fallback/Dockerfile"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

info() {
  echo -e "${GREEN}[INFO]${NC}  $*"
}

error() {
  echo -e "${RED}[ERROR]${NC} $*" >&2
  exit 1
}

for bin in docker go python3; do
  command -v "$bin" >/dev/null 2>&1 || error "$bin not found in PATH"
done
docker info >/dev/null 2>&1 || error "docker daemon is not running"
[[ -f "$FALLBACK_DOCKERFILE" ]] || error "Dockerfile not found: $FALLBACK_DOCKERFILE"

TMP_DIR="$(mktemp -d)"
IMAGES_TO_CLEAN=()

cleanup() {
  rm -rf "$TMP_DIR"
  if [[ "$KEEP_IMAGES" != "1" && ${#IMAGES_TO_CLEAN[@]} -gt 0 ]]; then
    docker image rm -f "${IMAGES_TO_CLEAN[@]}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

build_binary() {
  local src="$1"
  local out="$2"

  [[ -f "$src" ]] || error "source file not found: $src"
  CGO_ENABLED=0 GOOS=linux GOARCH="$GOARCH_OVERRIDE" \
    go build -trimpath -buildvcs=false -ldflags='-s -w -buildid=' -o "$out" "$src"
  touch -d "@${SOURCE_DATE_EPOCH}" "$out"
}

build_image_from_binary() {
  local tag="$1"
  local bin_path="$2"
  local ctx_dir="$3"

  mkdir -p "$ctx_dir"
  cp "$FALLBACK_DOCKERFILE" "$ctx_dir/Dockerfile"
  cp "$bin_path" "$ctx_dir/manager"
  touch -d "@${SOURCE_DATE_EPOCH}" "$ctx_dir/Dockerfile" "$ctx_dir/manager"

  docker build --no-cache -f "$ctx_dir/Dockerfile" --build-arg MANAGER_BIN=manager -t "$tag" "$ctx_dir" >/dev/null 2>&1
  IMAGES_TO_CLEAN+=("$tag")
}

image_fingerprint() {
  local tag="$1"
  docker image inspect "$tag" | python3 -c '
import hashlib
import json
import sys

obj = json.load(sys.stdin)[0]
cfg = obj.get("Config", {})
stable = {
    "Architecture": obj.get("Architecture"),
    "Os": obj.get("Os"),
    "RootFS": obj.get("RootFS"),
    "Config": {
        "Cmd": cfg.get("Cmd"),
        "Entrypoint": cfg.get("Entrypoint"),
        "Env": cfg.get("Env"),
        "ExposedPorts": cfg.get("ExposedPorts"),
        "Labels": cfg.get("Labels"),
        "User": cfg.get("User"),
        "WorkingDir": cfg.get("WorkingDir"),
    },
}
blob = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
print(hashlib.sha256(blob).hexdigest())
'
}

run_target_check() {
  local name="$1"
  local src="$2"

  local target_dir="$TMP_DIR/$name"
  mkdir -p "$target_dir"

  local bin_a="$target_dir/${name}-a"
  local bin_b="$target_dir/${name}-b"
  local ctx_a="$target_dir/context-a"
  local ctx_b="$target_dir/context-b"
  local tag_a="${IMAGE_PREFIX}/${name}:a"
  local tag_b="${IMAGE_PREFIX}/${name}:b"

  info "[$name] build #1"
  build_binary "$src" "$bin_a"
  build_image_from_binary "$tag_a" "$bin_a" "$ctx_a"

  info "[$name] build #2"
  build_binary "$src" "$bin_b"
  build_image_from_binary "$tag_b" "$bin_b" "$ctx_b"

  local bin_sha_a
  local bin_sha_b
  bin_sha_a="$(sha256sum "$bin_a" | awk '{print $1}')"
  bin_sha_b="$(sha256sum "$bin_b" | awk '{print $1}')"

  if [[ "$bin_sha_a" != "$bin_sha_b" ]]; then
    error "[$name] binary checksum mismatch: $bin_sha_a != $bin_sha_b"
  fi

  local fp_a
  local fp_b
  fp_a="$(image_fingerprint "$tag_a")"
  fp_b="$(image_fingerprint "$tag_b")"

  if [[ "$fp_a" != "$fp_b" ]]; then
    error "[$name] image fingerprint mismatch: $fp_a != $fp_b"
  fi

  info "[$name] reproducible: binary sha=${bin_sha_a}, image fp=${fp_a}"
}

run_target_check "mesh-operator-fallback" "$REPO_ROOT/scripts/ops/mesh_operator_fallback_manager/main.go"
run_target_check "mesh-node-fallback" "$REPO_ROOT/scripts/ops/mesh_node_fallback_manager/main.go"

info "Docker image reproducibility checks passed."
