#!/bin/bash
# Production Run Script for x0tta6bl4 MaaS (Host Native)

# 1. Environment Configuration
export PYTHONPATH=$PYTHONPATH:.
export DATABASE_URL="sqlite:///./x0tta6bl4_enterprise.db"
export X0TTA6BL4_PRODUCTION="true"
export PORT=8010

# Secret placeholders (should be set in shell or .env)
: "${STRIPE_SECRET_KEY:?STRIPE_SECRET_KEY must be set for production run}"
: "${VAULT_TOKEN:?VAULT_TOKEN must be set for production run}"
export STRIPE_SECRET_KEY
export VAULT_TOKEN

# 2. Preparation
mkdir -p logs
source venv/bin/activate

echo "📂 Applying Database Migrations..."
alembic upgrade head

# 3. Execution
echo "🚀 Starting MaaS Enterprise Control Plane on port $PORT..."
nohup uvicorn src.core.app:app --host 0.0.0.0 --port $PORT --workers 4 > logs/maas.log 2>&1 &
CP_PID=$!
echo $CP_PID > .maas_cp.pid

echo "🧹 Starting Marketplace Janitor..."
nohup python src/services/run_janitor.py > logs/janitor.log 2>&1 &
JAN_PID=$!
echo $JAN_PID > .maas_janitor.pid

echo "✅ MaaS Enterprise is now running in the background."
echo "   - Control Plane PID: $CP_PID"
echo "   - Janitor PID: $JAN_PID"
echo "   - Logs: logs/maas.log, logs/janitor.log"
echo "   - URL: http://localhost:$PORT"
