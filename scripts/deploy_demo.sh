#!/bin/bash
# Deploy Causal Analysis Demo Dashboard
# Options: Local, VPS, GitHub Pages

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/web/demo"

echo "=========================================="
echo "Causal Analysis Demo Deployment"
echo "=========================================="
echo ""

# Check deployment target
DEPLOY_TARGET="${1:-local}"

case "$DEPLOY_TARGET" in
    local)
        echo "📍 Local Deployment"
        echo ""
        echo "Starting server on http://localhost:8000"
        echo "Dashboard: http://localhost:8000/demo/causal-dashboard.html"
        echo ""
        cd "$PROJECT_ROOT"
        python -m src.core.app
        ;;
    
    vps)
        echo "📍 VPS Deployment"
        echo ""
        read -p "Enter VPS host (user@host): " VPS_HOST
        read -p "Enter deployment path (default: /var/www/causal-demo): " DEPLOY_PATH
        DEPLOY_PATH="${DEPLOY_PATH:-/var/www/causal-demo}"
        
        echo "Deploying to $VPS_HOST:$DEPLOY_PATH"
        
        # Create deployment directory
        ssh "$VPS_HOST" "mkdir -p $DEPLOY_PATH"
        
        # Copy files
        scp -r "$WEB_DIR"/* "$VPS_HOST:$DEPLOY_PATH/"
        scp -r "$PROJECT_ROOT/src" "$VPS_HOST:$DEPLOY_PATH/"
        scp "$PROJECT_ROOT/pyproject.toml" "$VPS_HOST:$DEPLOY_PATH/"
        
        # Setup systemd service (optional)
        echo ""
        echo "✅ Files deployed. Next steps:"
        echo "1. SSH to $VPS_HOST"
        echo "2. Install dependencies: cd $DEPLOY_PATH && pip install -e ."
        echo "3. Start server: python -m src.core.app"
        echo "4. Setup nginx/apache for HTTPS"
        ;;
    
    docker)
        echo "📍 Docker Deployment"
        echo ""
        echo "Building Docker image..."
        cd "$PROJECT_ROOT"
        
        # Create Dockerfile if not exists
        if [ ! -f Dockerfile ]; then
            cat > Dockerfile <<EOF
FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["python", "-m", "src.core.app"]
EOF
        fi
        
        docker build -t x0tta6bl4-demo:latest .
        
        echo ""
        echo "✅ Docker image built. Run with:"
        echo "docker run -p 8000:8000 x0tta6bl4-demo:latest"
        ;;
    
    github-pages)
        echo "📍 GitHub Pages Deployment"
        echo ""
        echo "Note: GitHub Pages only serves static files."
        echo "You'll need to host API separately or use mock data."
        echo ""
        read -p "Enter GitHub repo (user/repo): " GITHUB_REPO
        
        # Create gh-pages branch structure
        git checkout -b gh-pages 2>/dev/null || git checkout gh-pages
        
        # Copy demo files
        mkdir -p docs/demo
        cp -r "$WEB_DIR"/* docs/demo/
        
        # Create index redirect
        cat > docs/demo/index.html <<EOF
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url=causal-dashboard.html">
</head>
<body>
    <p>Redirecting to <a href="causal-dashboard.html">Causal Dashboard</a></p>
</body>
</html>
EOF
        
        git add docs/
        git commit -m "Deploy causal analysis demo to GitHub Pages" || true
        
        echo ""
        echo "✅ Ready to push. Run:"
        echo "git push origin gh-pages"
        echo ""
        echo "Demo will be available at:"
        echo "https://$(echo $GITHUB_REPO | cut -d'/' -f1).github.io/$(echo $GITHUB_REPO | cut -d'/' -f2)/demo/causal-dashboard.html"
        ;;
    
    *)
        echo "Usage: $0 [local|vps|docker|github-pages]"
        echo ""
        echo "Options:"
        echo "  local         - Run locally (default)"
        echo "  vps          - Deploy to VPS via SSH"
        echo "  docker       - Build and run Docker container"
        echo "  github-pages - Deploy to GitHub Pages (static only)"
        exit 1
        ;;
esac

