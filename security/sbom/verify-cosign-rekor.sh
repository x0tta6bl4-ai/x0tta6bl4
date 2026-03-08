#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/security/sbom/out"
TOOL_MODE="${TOOL_MODE:-auto}"
MODE="mock"

usage() {
  cat <<'EOF'
Usage:
  verify-cosign-rekor.sh [--mode mock|ci-keyless] [--tool-mode auto|native|docker]

Modes:
  mock        Local developer mode. Generates an ephemeral key pair, signs SBOM blobs,
              and verifies the signatures locally. No Rekor upload is attempted.
  ci-keyless  CI-only mode. Requires SIGSTORE_ID_TOKEN plus native cosign and rekor-cli.
              Signs blobs keylessly and uploads them to Rekor.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
    --tool-mode)
      TOOL_MODE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

artifacts=(
  "${OUTPUT_DIR}/agent.cdx.json"
  "${OUTPUT_DIR}/repo.cdx.json"
  "${OUTPUT_DIR}/repo.spdx.json"
  "${ROOT_DIR}/RC1_MANIFEST.json"
  "${ROOT_DIR}/RC1_RELEASE_NOTES.md"
  "${ROOT_DIR}/docs/release/RC1_INTEGRITY_NOTE.md"
)

for artifact in "${artifacts[@]}"; do
  [[ -f "${artifact}" ]] || {
    echo "missing artifact: ${artifact}" >&2
    exit 1
  }
done

if [[ "${TOOL_MODE}" == "auto" ]]; then
  if [[ "${MODE}" == "ci-keyless" ]]; then
    TOOL_MODE="native"
  elif command -v cosign >/dev/null 2>&1; then
    TOOL_MODE="native"
  else
    TOOL_MODE="docker"
  fi
fi

run_cosign() {
  if [[ "${TOOL_MODE}" == "native" ]]; then
    cosign "$@"
  else
    docker run --rm \
      -u "$(id -u):$(id -g)" \
      -e COSIGN_PASSWORD="${COSIGN_PASSWORD:-}" \
      -e HOME=/tmp \
      -v "${ROOT_DIR}:/workspace" \
      -w /workspace \
      ghcr.io/sigstore/cosign/cosign:v2.4.1 "$@"
  fi
}

# Translate a host-side absolute path to its equivalent inside the Docker
# container (where ROOT_DIR is mounted at /workspace).
cpath() {
  if [[ "${TOOL_MODE}" == "docker" ]]; then
    echo "${1/#${ROOT_DIR}//workspace}"
  else
    echo "${1}"
  fi
}

require_native() {
  local tool
  for tool in "$@"; do
    command -v "${tool}" >/dev/null 2>&1 || {
      echo "missing native tool: ${tool}" >&2
      exit 1
    }
  done
}

case "${MODE}" in
  mock)
    if [[ "${TOOL_MODE}" == "docker" ]]; then
      command -v docker >/dev/null 2>&1 || {
        echo "docker is required for mock docker mode" >&2
        exit 1
      }
    else
      require_native cosign
    fi
    export COSIGN_PASSWORD=""
    key_prefix="${OUTPUT_DIR}/mock-cosign"
    if [[ ! -f "${key_prefix}.key" || ! -f "${key_prefix}.pub" ]]; then
      run_cosign generate-key-pair --output-key-prefix "$(cpath "${key_prefix}")"
    fi
    for artifact in "${artifacts[@]}"; do
      run_cosign sign-blob \
        --yes \
        --key "$(cpath "${key_prefix}.key")" \
        --tlog-upload=false \
        --output-signature "$(cpath "${artifact}.sig")" \
        "$(cpath "${artifact}")"
      run_cosign verify-blob \
        --key "$(cpath "${key_prefix}.pub")" \
        --insecure-ignore-tlog \
        --signature "$(cpath "${artifact}.sig")" \
        "$(cpath "${artifact}")"
    done
    cat > "${OUTPUT_DIR}/mock-signing-status.txt" <<EOF
mode=mock
rekor=skipped
timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
artifacts_signed=${#artifacts[@]}
proves=local key pair generation, blob signing, local signature verification
does_not_prove=keyless OIDC signing, Rekor transparency-log upload, supply-chain attestation
to_claim_rekor=run in CI with: security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native
EOF
    echo ""
    echo "MOCK-ONLY — what this run proved:"
    echo "  + ephemeral key pair generated at ${OUTPUT_DIR}/mock-cosign.{key,pub}"
    echo "  + SBOM blobs signed and signatures verified locally"
    echo "  - Rekor transparency-log upload: SKIPPED (no OIDC token)"
    echo "  - Keyless cosign: SKIPPED (no SIGSTORE_ID_TOKEN)"
    echo "  Status written to: ${OUTPUT_DIR}/mock-signing-status.txt"
    echo ""
    echo "To claim transparency-log inclusion run in CI:"
    echo "  security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native"
    ;;
  ci-keyless)
    if [[ "${TOOL_MODE}" == "docker" ]]; then
      command -v docker >/dev/null 2>&1 || {
        echo "docker is required for ci-keyless docker mode" >&2
        exit 1
      }
    else
      require_native cosign
    fi

    : "${SIGSTORE_ID_TOKEN:?SIGSTORE_ID_TOKEN is required for ci-keyless mode}"

    for artifact in "${artifacts[@]}"; do
      # Sign keylessly using the identity token (OIDC-based)
      run_cosign sign-blob \
        --yes \
        --identity-token "${SIGSTORE_ID_TOKEN}" \
        --output-signature "$(cpath "${artifact}.sig")" \
        --output-certificate "$(cpath "${artifact}.crt")" \
        "$(cpath "${artifact}")"

      echo "Keyless signature and certificate created for: ${artifact}"
      
      # Verification through Rekor (Public Sigstore instance)
      run_cosign verify-blob \
        --certificate "$(cpath "${artifact}.crt")" \
        --signature "$(cpath "${artifact}.sig")" \
        --certificate-identity "https://github.com/x0tta6bl4/x0tta6bl4/.github/workflows/ci.yml@refs/heads/main" \
        --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
        "$(cpath "${artifact}")"
    done

    cat > "${OUTPUT_DIR}/keyless-signing-status.txt" <<EOF
mode=ci-keyless
rekor=uploaded
timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
artifacts_signed=${#artifacts[@]}
proves=keyless OIDC signing, Rekor transparency-log upload, supply-chain attestation
OIDC_ISSUER=https://token.actions.githubusercontent.com
EOF
    ;;
  *)
    echo "unsupported mode: ${MODE}" >&2
    exit 1
    ;;
esac

if [[ "${MODE}" == "mock" ]]; then
  echo "cosign signing completed: MOCK mode (local key only — Rekor NOT involved)"
else
  echo "cosign/rekor signing completed: CI-KEYLESS mode (Rekor upload attempted)"
fi
