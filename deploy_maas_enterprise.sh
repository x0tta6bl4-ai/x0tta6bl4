#!/usr/bin/env bash
# deploy_maas_enterprise.sh — production-safe launcher for MaaS Enterprise.

set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/mnt/projects}"
VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/venv}"
APP_MODULE="${APP_MODULE:-src.core.app:app}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-4}"
LIMIT_CONCURRENCY="${LIMIT_CONCURRENCY:-1000}"
KEEP_ALIVE_TIMEOUT="${KEEP_ALIVE_TIMEOUT:-60}"
LOG_LEVEL="${LOG_LEVEL:-info}"
MIN_FREE_RAM_MB="${MIN_FREE_RAM_MB:-500}"

require_env() {
    local name="$1"
    if [ -z "${!name:-}" ]; then
        echo "❌ Required environment variable is missing: $name" >&2
        exit 1
    fi
}

detect_free_ram_mb() {
    local value
    value="$(free -m | awk '/^Mem:/ {print $7; exit}')"
    if [ -z "${value:-}" ]; then
        value="$(free -m | awk '/^Память:/ {print $7; exit}')"
    fi
    if [[ ! "$value" =~ ^[0-9]+$ ]]; then
        value=0
    fi
    printf '%s\n' "$value"
}

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "❌ Python virtualenv not found: $VENV_PATH" >&2
    echo "Create it first: python3 -m venv \"$VENV_PATH\"" >&2
    exit 1
fi

FREE_RAM_MB="$(detect_free_ram_mb)"
echo "📊 Free RAM: ${FREE_RAM_MB}MB"
if [ "$FREE_RAM_MB" -lt "$MIN_FREE_RAM_MB" ]; then
    echo "❌ Not enough free RAM: ${FREE_RAM_MB}MB < ${MIN_FREE_RAM_MB}MB" >&2
    exit 1
fi

source "$VENV_PATH/bin/activate"
cd "$PROJECT_ROOT"

export PYTHONPATH="$PROJECT_ROOT"
export ENVIRONMENT="${ENVIRONMENT:-production}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$PROJECT_ROOT/x0tta6bl4_enterprise.db}"
export APP_DOMAIN="${APP_DOMAIN:-https://app.x0tta6bl4.net}"
export MAAS_LIGHT_MODE="${MAAS_LIGHT_MODE:-false}"

# Always require admin token because protected endpoints and middleware depend on it.
require_env ADMIN_TOKEN

# Strict secret requirements for production startup.
if [ "$ENVIRONMENT" = "production" ]; then
    require_env FLASK_SECRET_KEY
    require_env JWT_SECRET_KEY
    require_env CSRF_SECRET_KEY
    require_env OPERATOR_PRIVATE_KEY
fi

echo "🚀 Launching MaaS Enterprise..."
echo "Environment: $ENVIRONMENT"
echo "DB: $DATABASE_URL"

exec uvicorn "$APP_MODULE" \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --timeout-keep-alive "$KEEP_ALIVE_TIMEOUT" \
    --limit-concurrency "$LIMIT_CONCURRENCY" \
    --log-level "$LOG_LEVEL"
