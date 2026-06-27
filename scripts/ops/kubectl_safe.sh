#!/usr/bin/env bash
set -euo pipefail

# Safe kubectl wrapper:
# 1) use a real local kubectl binary (prefer kubectl-real)
# 2) fallback to dockerized kubectl if local binary is blocked by snap confinement
#
# Usage:
#   scripts/ops/kubectl_safe.sh config current-context

KUBECTL_IMAGE="${KUBECTL_IMAGE:-bitnami/kubectl:1.30.5}"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"

run_docker_kubectl() {
  local kubeconfig_path
  kubeconfig_path="${KUBECONFIG:-$HOME/.kube/config}"
  if [[ ! -f "$kubeconfig_path" ]]; then
    echo "[kubectl_safe] kubeconfig file not found: $kubeconfig_path" >&2
    return 1
  fi

  docker run --rm \
    -v "$kubeconfig_path:/kubeconfig:ro" \
    -e KUBECONFIG=/kubeconfig \
    "$KUBECTL_IMAGE" "$@"
}

find_local_kubectl() {
  local candidate candidate_real

  # Standalone binary installed by us takes precedence over snap.
  if command -v kubectl-real >/dev/null 2>&1; then
    command -v kubectl-real
    return 0
  fi

  while IFS= read -r candidate; do
    [[ -z "$candidate" ]] && continue
    candidate_real="$(readlink -f "$candidate" 2>/dev/null || printf '%s' "$candidate")"
    # Avoid recursion when this wrapper itself is on PATH as "kubectl".
    if [[ "$candidate_real" == "$SCRIPT_PATH" ]]; then
      continue
    fi
    printf '%s\n' "$candidate"
    return 0
  done < <(type -aP kubectl 2>/dev/null || true)

  return 1
}

LOCAL_KUBECTL="$(find_local_kubectl || true)"
if [[ -z "${LOCAL_KUBECTL}" ]]; then
  echo "[kubectl_safe] local kubectl not found; using docker image ${KUBECTL_IMAGE}" >&2
  run_docker_kubectl "$@"
  exit $?
fi

stderr_file="$(mktemp)"
trap 'rm -f "$stderr_file"' EXIT

if "$LOCAL_KUBECTL" "$@" 2>"$stderr_file"; then
  exit 0
fi

if grep -Eq "snap-confine|cap_dac_override" "$stderr_file"; then
  echo "[kubectl_safe] local kubectl blocked by snap confinement; falling back to docker image ${KUBECTL_IMAGE}" >&2
  run_docker_kubectl "$@"
  exit $?
fi

cat "$stderr_file" >&2
exit 1
