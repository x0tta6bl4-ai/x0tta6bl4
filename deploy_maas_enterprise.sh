#!/bin/bash
# deploy_maas_enterprise.sh — x0tta6bl4 Production Deployment
# Using VENV on secondary disk for maximum stability and space.

set -e

PROJECT_ROOT="/mnt/projects"
VENV_PATH="$PROJECT_ROOT/venv"

# --- 1. Resource Pre-flight Check ---
FREE_RAM=$(free -m | awk '/^Память:/{print $7}' || free -m | awk '/^Mem:/{print $7}')
echo "📊 Checking system resources..."
echo "Available RAM: ${FREE_RAM}MB"

if [ "$FREE_RAM" -lt 500 ]; then
    echo "❌ CRITICAL: Not enough free memory (< 500MB). Aborting."
    exit 1
fi

DISK_SPACE=$(df -h $PROJECT_ROOT | tail -1 | awk '{print $4}')
echo "Free space on $PROJECT_ROOT: $DISK_SPACE"

# --- 2. Virtual Environment ---
if [ ! -d "$VENV_PATH" ]; then
    echo "创建 Virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
fi

echo "🔌 Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# --- 3. Dependency Install ---
echo "📦 Installing/Updating dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet stripe authlib uvicorn

# --- 4. Environment Setup ---
echo "⚙️ Setting up environment..."
export DATABASE_URL="sqlite:///$PROJECT_ROOT/x0tta6bl4_enterprise.db"
export ADMIN_TOKEN=${ADMIN_TOKEN:-"$(openssl rand -hex 16)"}
export APP_DOMAIN="https://app.x0tta6bl4.net"

# --- 5. Database Init ---
echo "💾 Initializing Enterprise Database..."
python3 init_db.py

# --- 6. Launch ---
echo "✅ Deployment successful."
echo "Admin Token for this session: $ADMIN_TOKEN"
echo "Starting MaaS Enterprise Server on port 8000..."

exec uvicorn src.core.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --limit-concurrency 1000
