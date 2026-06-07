#!/bin/sh
set -eu

HOST="127.0.0.1"
PORT="8001"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      HOST="${2:-127.0.0.1}"
      shift 2
      ;;
    --port)
      PORT="${2:-8001}"
      shift 2
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      exit 64
      ;;
  esac
done

ROOT="${X0TTA6BL4_PROJECT_ROOT:-}"
APP_MODULE="${X0TTA6BL4_FULL_CORE_API_APP_MODULE:-src.core.app:app}"

if [ -z "$ROOT" ] || [ ! -f "$ROOT/src/core/app.py" ]; then
  for candidate in /opt/x0tta6bl4 /mnt/projects; do
    if [ -f "$candidate/src/core/app.py" ]; then
      ROOT="$candidate"
      break
    fi
  done
fi

if [ -z "$ROOT" ] || [ ! -f "$ROOT/src/core/app.py" ]; then
  echo "Full Core API source is missing. Checked X0TTA6BL4_PROJECT_ROOT, /opt/x0tta6bl4, and /mnt/projects." >&2
  exit 78
fi

PYTHON_BIN="${X0TTA6BL4_PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"
export MAAS_LIGHT_MODE="${MAAS_LIGHT_MODE:-true}"

exec "$PYTHON_BIN" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
