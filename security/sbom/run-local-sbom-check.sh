#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/security/sbom/out"
GO_SBOM="${OUTPUT_DIR}/agent.cdx.json"
REPO_CDX="${OUTPUT_DIR}/repo.cdx.json"
REPO_SPDX="${OUTPUT_DIR}/repo.spdx.json"
TOOL_MODE="${TOOL_MODE:-auto}"
COMMAND="full"
SBOM_GRYPE_TIMEOUT_SEC="${SBOM_GRYPE_TIMEOUT_SEC:-180}"
SBOM_GRYPE_DB_CACHE_DIR="${SBOM_GRYPE_DB_CACHE_DIR:-${OUTPUT_DIR}/grype-db}"
SBOM_GRYPE_DB_UPDATE_TIMEOUT_SEC="${SBOM_GRYPE_DB_UPDATE_TIMEOUT_SEC:-180}"
SBOM_GRYPE_DB_UPDATE_AVAILABLE_TIMEOUT="${SBOM_GRYPE_DB_UPDATE_AVAILABLE_TIMEOUT:-15s}"
SBOM_GRYPE_DB_UPDATE_DOWNLOAD_TIMEOUT="${SBOM_GRYPE_DB_UPDATE_DOWNLOAD_TIMEOUT:-5m}"

usage() {
  cat <<'EOF'
Usage:
  run-local-sbom-check.sh [generate|gate|full] [--tool-mode auto|native|docker]

Modes:
  generate  Build CycloneDX/SPDX SBOM artifacts
  gate      Scan existing SBOM artifacts and fail on HIGH/CRITICAL or CVSS >= 7.0
  full      Run generate then gate

Tool modes:
  native    Use locally installed tools (expected in CI jobs)
  docker    Use Docker container images where possible
  auto      Prefer native if all required tools exist, else fall back to docker
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    generate|gate|full)
      COMMAND="$1"
      shift
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

mkdir -p "${OUTPUT_DIR}"

detect_tool_mode() {
  if [[ "${TOOL_MODE}" != "auto" ]]; then
    return
  fi

  if command -v cyclonedx-gomod >/dev/null 2>&1 \
    && command -v syft >/dev/null 2>&1 \
    && command -v grype >/dev/null 2>&1 \
    && command -v python3 >/dev/null 2>&1; then
    TOOL_MODE="native"
    return
  fi

  if command -v docker >/dev/null 2>&1; then
    TOOL_MODE="docker"
    return
  fi

  echo "no usable toolchain found; install native tools or Docker" >&2
  exit 1
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

generate_native() {
  require_native cyclonedx-gomod syft python3
  if [[ ! -d "${ROOT_DIR}/agent" ]]; then
    echo "WARNING: agent/ module directory not found at ${ROOT_DIR}/agent — skipping Go SBOM" >&2
    echo "  The Go SBOM (agent.cdx.json) will not be generated." >&2
    echo "  Run from the repository root that contains the agent/ Go module." >&2
  else
    (
      cd "${ROOT_DIR}/agent"
      cyclonedx-gomod mod -licenses -json -output "${GO_SBOM}"
    )
  fi
  syft "dir:${ROOT_DIR}" -o "cyclonedx-json=${REPO_CDX}"
  syft "dir:${ROOT_DIR}" -o "spdx-json=${REPO_SPDX}"
}

generate_docker() {
  command -v docker >/dev/null 2>&1 || {
    echo "docker is required for docker tool mode" >&2
    exit 1
  }

  if [[ ! -d "${ROOT_DIR}/agent" ]]; then
    echo "WARNING: agent/ module directory not found at ${ROOT_DIR}/agent — skipping Go SBOM" >&2
    echo "  The Go SBOM (agent.cdx.json) will not be generated." >&2
  else
    docker run --rm \
      -v "${ROOT_DIR}:/workspace" \
      -w /workspace/agent \
      golang:1.24-bookworm \
      bash -c '
        set -euo pipefail
        export GOBIN=/tmp/bin
        export PATH="/usr/local/go/bin:/tmp/bin:${PATH}"
        go install github.com/CycloneDX/cyclonedx-gomod/cmd/cyclonedx-gomod@v1.8.0
        cyclonedx-gomod mod -licenses -json -output /workspace/security/sbom/out/agent.cdx.json
      '
  fi

  # Build a minimal staging dir with only the dependency manifests so that
  # syft completes in seconds rather than scanning the full repo tree.
  local SBOM_STAGE
  SBOM_STAGE="$(mktemp -d)"
  for f in go.mod go.sum requirements.txt pyproject.toml; do
    [[ -f "${ROOT_DIR}/${f}" ]] && cp "${ROOT_DIR}/${f}" "${SBOM_STAGE}/"
  done

  docker run --rm \
    -v "${SBOM_STAGE}:/inputs:ro" \
    -v "${OUTPUT_DIR}:/out" \
    anchore/syft:latest \
    "dir:/inputs" -o "cyclonedx-json=/out/repo.cdx.json"

  docker run --rm \
    -v "${SBOM_STAGE}:/inputs:ro" \
    -v "${OUTPUT_DIR}:/out" \
    anchore/syft:latest \
    "dir:/inputs" -o "spdx-json=/out/repo.spdx.json"

  rm -rf "${SBOM_STAGE}"
}

gate_with_grype() {
  local sbom="$1"
  local report="${sbom}.grype.json"
  shift
  local scan_rc=0

  set +e
  "$@" > "${report}"
  scan_rc=$?
  set -e

  if [[ "${scan_rc}" -ne 0 ]]; then
    rm -f "${report}"
    if [[ "${scan_rc}" -eq 124 ]]; then
      echo "grype scan timed out after ${SBOM_GRYPE_TIMEOUT_SEC}s for ${sbom}" >&2
    else
      echo "grype scan failed for ${sbom} (exit ${scan_rc})" >&2
    fi
    return "${scan_rc}"
  fi

  python3 - "${report}" <<'PY'
import json
import sys

report_path = sys.argv[1]
with open(report_path, "r", encoding="utf-8") as fh:
    report = json.load(fh)

matches = []
for match in report.get("matches", []):
    vuln = match.get("vulnerability") or {}
    severity = (vuln.get("severity") or "").lower()
    cvss_scores = [
        entry.get("metrics", {}).get("baseScore", 0)
        for entry in vuln.get("cvss", [])
        if isinstance(entry, dict)
    ]
    max_cvss = max(cvss_scores or [0])
    if severity in {"high", "critical"} or max_cvss >= 7:
        matches.append({
            "id": vuln.get("id"),
            "severity": vuln.get("severity"),
            "cvss": max_cvss,
            "package": (match.get("artifact") or {}).get("name"),
            "installed": (match.get("artifact") or {}).get("version"),
            "fix": ((vuln.get("fix") or {}).get("versions") or []),
        })

if matches:
    print(json.dumps(matches, indent=2), file=sys.stderr)
    sys.exit(1)
PY
}

gate_native() {
  require_native grype python3
  local sbom
  for sbom in "${GO_SBOM}" "${REPO_CDX}" "${REPO_SPDX}"; do
    [[ -f "${sbom}" ]] || {
      echo "missing SBOM artifact: ${sbom}" >&2
      exit 1
    }
    gate_with_grype "${sbom}" grype "sbom:${sbom}" -o json
  done
}

prepare_grype_db_docker() {
  local update_rc=0

  mkdir -p "${SBOM_GRYPE_DB_CACHE_DIR}"

  if docker run --rm \
    -e GRYPE_DB_CACHE_DIR=/grype-db \
    -e GRYPE_DB_AUTO_UPDATE=false \
    -v "${SBOM_GRYPE_DB_CACHE_DIR}:/grype-db" \
    anchore/grype:latest db status >/dev/null 2>&1; then
    return 0
  fi

  echo "grype DB missing or invalid at ${SBOM_GRYPE_DB_CACHE_DIR}; attempting explicit update" >&2

  set +e
  timeout "${SBOM_GRYPE_DB_UPDATE_TIMEOUT_SEC}" docker run --rm \
    -e GRYPE_DB_CACHE_DIR=/grype-db \
    -e GRYPE_DB_UPDATE_AVAILABLE_TIMEOUT="${SBOM_GRYPE_DB_UPDATE_AVAILABLE_TIMEOUT}" \
    -e GRYPE_DB_UPDATE_DOWNLOAD_TIMEOUT="${SBOM_GRYPE_DB_UPDATE_DOWNLOAD_TIMEOUT}" \
    -v "${SBOM_GRYPE_DB_CACHE_DIR}:/grype-db" \
    anchore/grype:latest db update >/dev/null
  update_rc=$?
  set -e

  if [[ "${update_rc}" -ne 0 ]]; then
    if [[ "${update_rc}" -eq 124 ]]; then
      echo "grype DB update timed out after ${SBOM_GRYPE_DB_UPDATE_TIMEOUT_SEC}s" >&2
    else
      echo "grype DB update failed (exit ${update_rc})" >&2
    fi
    return "${update_rc}"
  fi

  docker run --rm \
    -e GRYPE_DB_CACHE_DIR=/grype-db \
    -e GRYPE_DB_AUTO_UPDATE=false \
    -v "${SBOM_GRYPE_DB_CACHE_DIR}:/grype-db" \
    anchore/grype:latest db status >/dev/null
}

gate_docker() {
  command -v docker >/dev/null 2>&1 || {
    echo "docker is required for docker tool mode" >&2
    exit 1
  }
  command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required to evaluate Grype JSON output" >&2
    exit 1
  }

  prepare_grype_db_docker

  local sbom rel
  for sbom in "${GO_SBOM}" "${REPO_CDX}" "${REPO_SPDX}"; do
    [[ -f "${sbom}" ]] || {
      echo "missing SBOM artifact: ${sbom}" >&2
      exit 1
    }
    rel="/workspace/${sbom#${ROOT_DIR}/}"
    gate_with_grype "${sbom}" timeout "${SBOM_GRYPE_TIMEOUT_SEC}" docker run --rm \
      -e GRYPE_DB_CACHE_DIR=/grype-db \
      -e GRYPE_DB_AUTO_UPDATE=false \
      -v "${SBOM_GRYPE_DB_CACHE_DIR}:/grype-db" \
      -v "${ROOT_DIR}:/workspace" \
      anchore/grype:latest "sbom:${rel}" -o json
  done
}

detect_tool_mode

case "${COMMAND}" in
  generate)
    if [[ "${TOOL_MODE}" == "native" ]]; then
      generate_native
    else
      generate_docker
    fi
    ;;
  gate)
    if [[ "${TOOL_MODE}" == "native" ]]; then
      gate_native
    else
      gate_docker
    fi
    ;;
  full)
    if [[ "${TOOL_MODE}" == "native" ]]; then
      generate_native
      gate_native
    else
      generate_docker
      gate_docker
    fi
    ;;
  *)
    echo "unsupported command: ${COMMAND}" >&2
    exit 1
    ;;
esac

echo "SBOM ${COMMAND} completed using ${TOOL_MODE} mode"
