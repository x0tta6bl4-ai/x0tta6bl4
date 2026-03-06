#!/usr/bin/env bash
set -euo pipefail

ROOT_CONTRACT="/mnt/projects/dao/qos/stake-multiplier.sol"
MIRROR_CONTRACT="/mnt/projects/src/dao/contracts/contracts/QoSManager.sol"

normalize() {
  local file="$1"
  sed -E \
    -e '/^[[:space:]]*pragma[[:space:]]+solidity/d' \
    -e '/^[[:space:]]*\/\/.*/d' \
    -e '/^[[:space:]]*\/\*\*/d' \
    -e '/^[[:space:]]*\*\//d' \
    -e '/^[[:space:]]*\*/d' \
    -e '/^[[:space:]]*$/d' \
    "$file" | tr -d '[:space:]'
}

root_normalized="$(normalize "$ROOT_CONTRACT")"
mirror_normalized="$(normalize "$MIRROR_CONTRACT")"

if [[ "$root_normalized" != "$mirror_normalized" ]]; then
  echo "QoS mirror drift detected between:"
  echo "  - $ROOT_CONTRACT"
  echo "  - $MIRROR_CONTRACT"
  diff -u "$ROOT_CONTRACT" "$MIRROR_CONTRACT" || true
  exit 1
fi

echo "QoS mirror sync check passed"
