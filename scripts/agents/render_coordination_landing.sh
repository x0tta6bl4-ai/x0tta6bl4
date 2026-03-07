#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEMPLATE="${ROOT_DIR}/docs/team/coordination-landing.template.md"
TARGET="${ROOT_DIR}/COORDINATION.md"

[[ -f "${TEMPLATE}" ]] || {
  echo "coordination template missing: ${TEMPLATE}" >&2
  exit 1
}

cp "${TEMPLATE}" "${TARGET}"
echo "rendered ${TARGET} from ${TEMPLATE}"
