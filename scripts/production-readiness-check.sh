#!/usr/bin/env bash
# Compatibility entrypoint. The real readiness logic lives in the fail-closed
# Python gate so shell output cannot accidentally claim production readiness
# from shallow file-existence checks.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT_DIR/scripts/ops/check_real_readiness.py" "$@"
