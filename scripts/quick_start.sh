#!/bin/bash
# Quick Start Script for x0tta6bl4
# Provides interactive menu for common operations

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     x0tta6bl4 v3.4 - Quick Start                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."
    
    MISSING=0
    
    if ! command -v python3 &> /dev/null; then
        echo "❌ python3 not found"
        MISSING=1
    else
        echo "✅ python3 found"
    fi
    
    if ! command -v kubectl &> /dev/null; then
        echo "⚠️  kubectl not found (optional for local development)"
    else
        echo "✅ kubectl found"
    fi
    
    if ! command -v helm &> /dev/null; then
        echo "⚠️  helm not found (optional for deployment)"
    else
        echo "✅ helm found"
    fi
    
    if [ $MISSING -eq 1 ]; then
        echo ""
        echo "❌ Missing required prerequisites. Please install them first."
        exit 1
    fi
    
    echo ""
}

# Check dependencies
check_dependencies() {
    echo "🔍 Checking dependencies..."
    python3 scripts/check_dependencies.py
    echo ""
}

# Local development setup
local_setup() {
    echo "🔧 Setting up local development environment..."
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install dependencies
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements-core.txt
    
    echo ""
    echo "✅ Local development environment ready!"
    echo "   Activate with: source venv/bin/activate"
    echo ""
}

# Run health checks
run_health_checks() {
    echo "🏥 Running health checks..."
    
    # Start application in background
    python3 -m uvicorn src.core.app:app --host 0.0.0.0 --port 8000 &
    APP_PID=$!
    
    sleep 5
    
    # Check health
    if curl -f http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ Health check passed"
        curl -s http://localhost:8000/health | jq '.' || curl -s http://localhost:8000/health
    else
        echo "❌ Health check failed"
    fi
    
    # Stop application
    kill $APP_PID 2>/dev/null || true
    
    echo ""
}

# Show menu
show_menu() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Select an option:"
    echo ""
    echo "1) Check prerequisites"
    echo "2) Check dependencies"
    echo "3) Setup local development"
    echo "4) Run health checks"
    echo "5) Validate cluster (requires kubectl)"
    echo "6) Deploy to staging (requires kubectl + helm)"
    echo "7) Show documentation"
    echo "8) Exit"
    echo ""
    read -p "Enter choice [1-8]: " choice
    
    case $choice in
        1)
            check_prerequisites
            show_menu
            ;;
        2)
            check_dependencies
            show_menu
            ;;
        3)
            local_setup
            show_menu
            ;;
        4)
            run_health_checks
            show_menu
            ;;
        5)
            if command -v kubectl &> /dev/null; then
                ./scripts/validate_cluster.sh
            else
                echo "❌ kubectl not found"
            fi
            show_menu
            ;;
        6)
            if command -v kubectl &> /dev/null && command -v helm &> /dev/null; then
                ./scripts/deploy_staging.sh latest
            else
                echo "❌ kubectl or helm not found"
            fi
            show_menu
            ;;
        7)
            echo ""
            echo "📚 Documentation:"
            echo "   - INSTALLATION_GUIDE.md"
            echo "   - README_INSTALLATION.md"
            echo "   - docs/operations/OPERATIONS_GUIDE.md"
            echo "   - docs/beta/BETA_TESTING_GUIDE.md"
            echo ""
            show_menu
            ;;
        8)
            echo "👋 Goodbye!"
            exit 0
            ;;
        *)
            echo "❌ Invalid choice"
            show_menu
            ;;
    esac
}

# Main
check_prerequisites
show_menu

