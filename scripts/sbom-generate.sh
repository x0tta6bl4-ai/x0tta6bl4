#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/artifacts/sbom"

mkdir -p "${OUTPUT_DIR}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 1
  fi
}

require_cmd cosign

if ! command -v cyclonedx-gomod >/dev/null 2>&1; then
  echo "missing required command: cyclonedx-gomod" >&2
  exit 1
fi

if ! command -v syft >/dev/null 2>&1; then
  echo "missing required command: syft" >&2
  exit 1
fi

GO_SBOM="${OUTPUT_DIR}/go-agent.cdx.json"
PY_SBOM="${OUTPUT_DIR}/python-monorepo.cdx.json"
SPDX_SBOM="${OUTPUT_DIR}/monorepo.spdx.json"

(
  cd "${ROOT_DIR}/agent"
  cyclonedx-gomod mod -licenses -json -output "${GO_SBOM}"
)

if command -v cyclonedx-py >/dev/null 2>&1; then
  cyclonedx-py environment --output-format JSON --output-file "${PY_SBOM}"
else
  syft "dir:${ROOT_DIR}" -o "cyclonedx-json=${PY_SBOM}" --select-catalogers python-package-cataloger
fi

syft "dir:${ROOT_DIR}" -o "spdx-json=${SPDX_SBOM}"

for artifact in "${GO_SBOM}" "${PY_SBOM}" "${SPDX_SBOM}"; do
  cosign sign-blob \
    --yes \
    --output-signature "${artifact}.sig" \
    --output-certificate "${artifact}.crt" \
    "${artifact}"
done

echo "SBOM artifacts written to ${OUTPUT_DIR}"
