#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME="${CONTAINER_RUNTIME:-docker}"
GO_IMAGE="${GO_IMAGE:-golang:1.24-bookworm}"
OUTPUT_BIN="${OUTPUT_BIN:-${ROOT_DIR}/ebpf/prod/loader}"

usage() {
  cat <<'EOF'
Usage:
  build-in-docker.sh [--runtime docker|podman] [--image <golang-image>] [--output <path>]

Builds ebpf/prod/loader inside a Go 1.24 container and writes the binary back to
the mounted workspace.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime) RUNTIME="$2"; shift 2 ;;
    --image)   GO_IMAGE="$2"; shift 2 ;;
    --output)  OUTPUT_BIN="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

command -v "${RUNTIME}" >/dev/null 2>&1 || {
  echo "container runtime not found: ${RUNTIME}" >&2
  exit 1
}

case "${RUNTIME}" in
  docker) docker info >/dev/null 2>&1 || { echo "docker daemon not reachable" >&2; exit 1; } ;;
  podman) podman info >/dev/null 2>&1 || { echo "podman runtime not reachable" >&2; exit 1; } ;;
esac

mkdir -p "$(dirname "${OUTPUT_BIN}")"

"${RUNTIME}" run --rm \
  -v "${ROOT_DIR}:/workspace" \
  -w /workspace/ebpf/prod \
  "${GO_IMAGE}" \
  bash -lc "set -euo pipefail; go build -o '${OUTPUT_BIN}' ."

echo "ebpf/prod loader built with ${RUNTIME} (${GO_IMAGE}) -> ${OUTPUT_BIN}"
