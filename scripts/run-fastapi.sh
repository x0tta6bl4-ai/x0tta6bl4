#!/bin/bash
# Quick launcher for x0tta6bl4 FastAPI application
# Usage: ./run-fastapi.sh

set -e

echo "🚀 Starting x0tta6bl4 FastAPI application..."
echo ""

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Check if key dependencies are installed, install if not
if ! python -c "import hvac" &> /dev/null; then
    echo "📦 Installing dependencies (this may take a minute)..."
    pip install --quiet -r requirements-staging.txt
    echo ""
    echo "✅ All dependencies installed"
    echo ""
else
    echo "✅ Dependencies already installed."
fi

echo "Starting FastAPI server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

# Run FastAPI with uvicorn
uvicorn src.core.app:app --host 0.0.0.0 --port 8000 --reload --log-level info
