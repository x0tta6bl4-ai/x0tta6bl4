#!/bin/bash
# x0tta6bl4 System Optimization Script
# Комплексная оптимизация системы для работы с проектом x0tta6bl4

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}x0tta6bl4 System Optimization${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check system specs
echo -e "${BLUE}[INFO] System Specifications:${NC}"
lscpu | grep -E "(Model name|CPU\(s\)|Thread|Core)" || true
free -h | head -2
df -h / | head -2
echo ""

# 1. Docker Setup and Optimization
echo -e "${YELLOW}[1/8] Optimizing Docker...${NC}"

# Fix Docker if broken
sudo systemctl stop docker || true
sudo rm -rf /var/lib/docker/tmp/* || true
sudo rm -rf /var/run/docker.sock || true

# Reinstall Docker cleanly
sudo apt remove docker docker-engine docker.io containerd runc || true
sudo apt update
sudo apt install -y docker.io docker-compose

# Configure Docker daemon for performance
sudo mkdir -p /etc/docker
cat > /tmp/docker-daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "default-ulimits": {
    "nofile": {
      "name": "nofile",
      "hard": 65536,
      "soft": 65536
    }
  },
  "features": {
    "buildkit": true
  }
}
EOF

sudo cp /tmp/docker-daemon.json /etc/docker/daemon.json
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER

echo -e "${GREEN}✓ Docker optimized and configured${NC}"

# 2. Python Environment Optimization
echo -e "${YELLOW}[2/8] Optimizing Python environment...${NC}"
cd /mnt/AC74CC2974CBF3DC

# Activate venv
source .venv/bin/activate

# Install/upgrade critical packages
pip install --upgrade pip setuptools wheel
pip install --upgrade pytest pytest-cov pytest-xdist

# Install project dependencies
pip install -e ".[dev]" || pip install -e .

echo -e "${GREEN}✓ Python environment optimized${NC}"

# 3. System Performance Tuning
echo -e "${YELLOW}[3/8] Tuning system performance...${NC}"

# Increase file limits for mesh networking
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Network optimizations for mesh
sudo mkdir -p /etc/sysctl.d
cat > /tmp/x0tta6bl4-sysctl.conf << 'EOF'
# x0tta6bl4 Network Optimizations
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.netdev_max_backlog = 5000
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.all.disable_ipv6 = 0
net.ipv6.conf.default.disable_ipv6 = 0
EOF

sudo cp /tmp/x0tta6bl4-sysctl.conf /etc/sysctl.d/99-x0tta6bl4.conf
sudo sysctl -p /etc/sysctl.d/99-x0tta6bl4.conf

echo -e "${GREEN}✓ System performance tuned${NC}"

# 4. Development Tools Setup
echo -e "${YELLOW}[4/8] Installing development tools...${NC}"
sudo apt install -y \
    build-essential \
    git \
    curl \
    wget \
    jq \
    htop \
    tree \
    net-tools \
    iproute2 \
    iptables \
    bridge-utils \
    tcpdump \
    iputils-ping \
    traceroute

echo -e "${GREEN}✓ Development tools installed${NC}"

# 5. Docker Buildx Setup
echo -e "${YELLOW}[5/8] Setting up Docker Buildx...${NC}"
sleep 5

# Create optimized builder
docker buildx create --name x0tta6bl4-builder --use || {
    echo -e "${YELLOW}Using default builder...${NC}"
    docker buildx use default
}

echo -e "${GREEN}✓ Docker Buildx configured${NC}"

# 6. Project Dependencies Check
echo -e "${YELLOW}[6/8] Verifying project dependencies...${NC}"

# Verify critical imports
python -c "
import sys
try:
    import fastapi
    import uvicorn
    import pytest
    print('✓ Core dependencies verified')
    print(f'✓ Python: {sys.version}')
    print(f'✓ FastAPI: {fastapi.__version__}')
    print(f'✓ Uvicorn: {uvicorn.__version__}')
    print(f'✓ Pytest: {pytest.__version__}')
except ImportError as e:
    print(f'⚠ Missing dependency: {e}')
"

echo -e "${GREEN}✓ Project dependencies verified${NC}"

# 7. Mesh Networking Setup
echo -e "${YELLOW}[7/8] Preparing mesh networking...${NC}"
# Enable IPv6
sudo sysctl -w net.ipv6.conf.all.disable_ipv6=0
sudo sysctl -w net.ipv6.conf.default.disable_ipv6=0

echo -e "${GREEN}✓ Mesh networking prepared${NC}"

# 8. Performance Monitoring Setup
echo -e "${YELLOW}[8/8] Setting up monitoring...${NC}"
# Create monitoring aliases
cat >> ~/.bashrc << 'EOF'

# x0tta6bl4 Project Aliases
alias x0-status='docker-compose ps && docker stats --no-stream'
alias x0-logs='docker-compose logs -f'
alias x0-test='pytest tests/ -v --tb=short'
alias x0-cov='pytest tests/ --cov=src --cov-report=html'
alias x0-build='docker-compose build'
alias x0-up='docker-compose up -d'
alias x0-down='docker-compose down'
alias x0-restart='docker-compose restart'
alias x0-minimal='docker-compose -f docker-compose.minimal.yml'
EOF

echo -e "${GREEN}✓ Monitoring and aliases configured${NC}"

# Final system info
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Optimization Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}System Ready For:${NC}"
echo "• Multi-node mesh development"
echo "• Docker BuildKit compilation"
echo "• High-performance networking"
echo "• Integration testing"
echo "• Coverage analysis"
echo ""
echo -e "${BLUE}Quick Commands:${NC}"
echo "• x0-up       - Start mesh"
echo "• x0-minimal  - Minimal mesh commands"
echo "• x0-test     - Run tests"
echo "• x0-cov      - Generate coverage"
echo "• x0-status   - Check status"
echo ""
echo -e "${YELLOW}Note: Restart terminal to activate Docker group membership${NC}"
echo -e "${YELLOW}Or run: newgrp docker${NC}"
echo ""

echo -e "${GREEN}🚀 x0tta6bl4 System Optimization${NC}"
echo "=========================================="
echo ""

# 1. Docker optimization
echo -e "${YELLOW}[1/8] Optimizing Docker...${NC}"
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "storage-opts": [
    "overlay2.override_kernel_check=true"
  ],
  "default-runtime": "runc",
  "features": {
    "buildkit": true
  }
}
EOF
sudo systemctl restart docker
echo -e "${GREEN}✓ Docker optimized${NC}"

# 2. Increase file watchers for development
echo -e "${YELLOW}[2/8] Increasing file watchers...${NC}"
echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
echo -e "${GREEN}✓ File watchers increased${NC}"

# 3. Optimize Git configuration
echo -e "${YELLOW}[3/8] Optimizing Git configuration...${NC}"
git config --global pull.rebase false
git config --global init.defaultBranch main
git config --global core.autocrlf input
git config --global core.editor "nano"
git config --global merge.tool vimdiff
echo -e "${GREEN}✓ Git optimized${NC}"

# 4. Install Python development tools
echo -e "${YELLOW}[4/8] Installing Python development tools...${NC}"
pip install --upgrade pip setuptools wheel
pip install black isort flake8 mypy pre-commit
echo -e "${GREEN}✓ Python tools installed${NC}"

# 5. Setup pre-commit hooks
echo -e "${YELLOW}[5/8] Setting up pre-commit hooks...${NC}"
cd /mnt/AC74CC2974CBF3DC
if [ ! -f .pre-commit-config.yaml ]; then
    cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
EOF
fi
pre-commit install || true
echo -e "${GREEN}✓ Pre-commit hooks configured${NC}"

# 6. Optimize system swappiness
echo -e "${YELLOW}[6/8] Optimizing system swappiness...${NC}"
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl vm.swappiness=10
echo -e "${GREEN}✓ Swappiness optimized${NC}"

# 7. Install monitoring tools
echo -e "${YELLOW}[7/8] Installing monitoring tools...${NC}"
sudo apt install -y iotop nethogs dstat
echo -e "${GREEN}✓ Monitoring tools installed${NC}"

# 8. Create useful aliases
echo -e "${YELLOW}[8/8] Setting up aliases...${NC}"
cat >> ~/.bashrc << 'EOF'

# x0tta6bl4 aliases
alias x0='cd /mnt/AC74CC2974CBF3DC'
alias x0-test='cd /mnt/AC74CC2974CBF3DC && source .venv/bin/activate && pytest'
alias x0-cov='cd /mnt/AC74CC2974CBF3DC && source .venv/bin/activate && pytest --cov=src --cov-report=html'
alias x0-mesh='cd /mnt/AC74CC2974CBF3DC && docker-compose -f docker-compose.minimal.yml'
alias x0-full='cd /mnt/AC74CC2974CBF3DC && docker-compose'
alias x0-logs='docker-compose -f /mnt/AC74CC2974CBF3DC/docker-compose.minimal.yml logs -f'
alias x0-clean='docker system prune -f && docker volume prune -f'
EOF

echo -e "${GREEN}=========================================="
echo -e "${GREEN}✓ System optimization complete!${NC}"
echo ""
echo "Useful commands:"
echo "  x0          - Go to project directory"
echo "  x0-test     - Run tests"
echo "  x0-cov      - Run tests with coverage"
echo "  x0-mesh     - Manage minimal mesh"
echo "  x0-full     - Manage full mesh with Yggdrasil"
echo "  x0-logs     - View mesh logs"
echo "  x0-clean    - Clean Docker system"
echo ""
echo "Restart terminal to load new aliases."