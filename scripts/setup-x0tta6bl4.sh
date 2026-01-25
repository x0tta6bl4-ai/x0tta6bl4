#!/bin/bash
# setup-x0tta6bl4.sh — полная подготовка окружения

set -e

echo "🚀 Инициализация x0tta6bl4 окружения..."

# Клонирование репозиториев
mkdir -p ~/x0tta6bl4 && cd ~/x0tta6bl4

if [ ! -d "mesh-architecture" ]; then
    git clone https://github.com/x0tta6bl4/mesh-architecture.git || echo "⚠️  Repository not found, skipping..."
fi

if [ ! -d "dao-contracts" ]; then
    git clone https://github.com/x0tta6bl4/dao-contracts.git || echo "⚠️  Repository not found, skipping..."
fi

if [ ! -d "toolkit" ]; then
    git clone https://github.com/x0tta6bl4/toolkit.git || echo "⚠️  Repository not found, skipping..."
fi

# Установка зависимостей
if [ -d "toolkit" ]; then
    cd toolkit
    pip install -r requirements.txt 2>/dev/null || echo "⚠️  pip install failed"
    npm install 2>/dev/null || echo "⚠️  npm install failed"
    cd ..
fi

# Docker setup для сетевого стека
if command -v docker-compose &> /dev/null; then
    if [ -f "docker-compose.mesh.yml" ]; then
        docker-compose -f docker-compose.mesh.yml up -d || echo "⚠️  Docker compose failed"
    fi
    if [ -f "docker-compose.observability.yml" ]; then
        docker-compose -f docker-compose.observability.yml up -d || echo "⚠️  Observability compose failed"
    fi
fi

# Kubernetes для CI/CD
if command -v kind &> /dev/null; then
    kind create cluster --name x0tta6bl4-test 2>/dev/null || echo "⚠️  Kind cluster already exists"
    kubectl apply -f k8s/namespace.yaml 2>/dev/null || echo "⚠️  K8s namespace not found"
fi

# eBPF инструменты
if [ ! -d "bcc" ]; then
    git clone https://github.com/iovisor/bcc.git 2>/dev/null || echo "⚠️  BCC clone failed"
    if [ -d "bcc" ]; then
        cd bcc
        ./install.sh 2>/dev/null || echo "⚠️  BCC install failed (may need sudo)"
        cd ..
    fi
fi

echo "✅ Окружение готово!"

