#!/usr/bin/env bash
# scripts/security-scan.sh
# Fail-closed security scan wrapper for Snyk and Trivy.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  security-scan.sh [--snyk] [--trivy] [--severity LEVELS] [--image IMAGE] [--output FILE]

Options:
  --snyk              Run Snyk scan.
  --trivy             Run Trivy scan.
  --severity LEVELS   Severity filter (default: HIGH,CRITICAL).
  --image IMAGE       Scan a container image instead of filesystem where supported.
  --output FILE       Tee output to file.
  -h, --help          Show help.

Notes:
  - If neither --snyk nor --trivy is provided, Trivy scan is run by default.
  - Script is fail-closed: missing scanner binary or detected findings return non-zero.
EOF
}

run_snyk=false
run_trivy=false
severity="HIGH,CRITICAL"
image=""
output=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snyk)
      run_snyk=true
      shift
      ;;
    --trivy)
      run_trivy=true
      shift
      ;;
    --severity)
      severity="${2:-}"
      shift 2
      ;;
    --image)
      image="${2:-}"
      shift 2
      ;;
    --output)
      output="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$severity" ]]; then
  echo "Severity must not be empty." >&2
  exit 2
fi

if ! $run_snyk && ! $run_trivy; then
  run_trivy=true
fi

if [[ -n "$output" ]]; then
  exec > >(tee "$output") 2>&1
fi

first_severity="$(echo "$severity" | cut -d',' -f1 | tr '[:upper:]' '[:lower:]')"

if $run_snyk; then
  if ! command -v snyk >/dev/null 2>&1; then
    echo "snyk binary not found in PATH." >&2
    exit 1
  fi

  echo "Running Snyk scan..."
  if [[ -n "$image" ]]; then
    snyk container test "$image" --severity-threshold="$first_severity"
  else
    snyk test --severity-threshold="$first_severity"
  fi
fi

if $run_trivy; then
  if ! command -v trivy >/dev/null 2>&1; then
    echo "trivy binary not found in PATH." >&2
    exit 1
  fi

  echo "Running Trivy scan..."
  if [[ -n "$image" ]]; then
    trivy image "$image" --severity "$severity" --ignore-unfixed --exit-code 1 --no-progress
  else
    trivy fs . --severity "$severity" --ignore-unfixed --exit-code 1 --no-progress
  fi
fi

echo "Security scan completed successfully."
