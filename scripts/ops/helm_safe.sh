#!/usr/bin/env bash
set -euo pipefail

# Safe Helm wrapper:
# 1) try local helm first
# 2) if local helm fails due snap confinement, fallback to dockerized helm
#
# Usage:
#   scripts/ops/helm_safe.sh lint charts/x0tta-mesh-operator

HELM_IMAGE="${HELM_IMAGE:-alpine/helm:3.15.4}"

run_docker_helm() {
  docker run --rm \
    -v "$PWD:/work" \
    -w /work \
    "$HELM_IMAGE" "$@"
}

if ! command -v helm >/dev/null 2>&1; then
  echo "[helm_safe] local helm not found; using docker image ${HELM_IMAGE}" >&2
  run_docker_helm "$@"
  exit $?
fi

stderr_file="$(mktemp)"
trap 'rm -f "$stderr_file"' EXIT

if helm "$@" 2>"$stderr_file"; then
  exit 0
fi

if rg -q "snap-confine|cap_dac_override" "$stderr_file"; then
  echo "[helm_safe] local helm blocked by snap confinement; falling back to docker image ${HELM_IMAGE}" >&2
  run_docker_helm "$@"
  exit $?
fi

cat "$stderr_file" >&2
exit 1
