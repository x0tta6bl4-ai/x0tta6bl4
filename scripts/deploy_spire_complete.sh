#!/bin/bash
# Полный deployment SPIRE для production
# Использование: ./scripts/deploy_spire_complete.sh

set -e

echo "🚀 SPIRE Deployment - Production Ready"
echo "========================================"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка зависимостей
check_dependencies() {
    echo "📋 Checking dependencies..."
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found${NC}"
        exit 1
    fi
    
    if ! command -v openssl &> /dev/null; then
        echo -e "${RED}❌ openssl not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Dependencies OK${NC}"
}

# Создание namespace
create_namespace() {
    echo ""
    echo "📦 Creating namespace..."
    kubectl create namespace spire --dry-run=client -o yaml | kubectl apply -f -
    echo -e "${GREEN}✅ Namespace created${NC}"
}

# Генерация CA сертификатов
generate_ca() {
    echo ""
    echo "🔐 Generating CA certificates..."
    
    mkdir -p /tmp/spire-certs
    cd /tmp/spire-certs
    
    # Генерация CA private key
    openssl genrsa -out ca.key 2048
    
    # Генерация CA certificate
    openssl req -new -x509 -days 365 -key ca.key -out ca.crt \
        -subj "/CN=spire-ca/O=x0tta6bl4"
    
    # Копирование в секреты
    kubectl create secret generic spire-ca \
        --from-file=ca.key=ca.key \
        --from-file=ca.crt=ca.crt \
        -n spire --dry-run=client -o yaml | kubectl apply -f -
    
    echo -e "${GREEN}✅ CA certificates generated${NC}"
}

# Deploy SPIRE Server
deploy_spire_server() {
    echo ""
    echo "🖥️  Deploying SPIRE Server..."
    
    # Применить манифест
    if [ -f "infra/security/spire-server-deployment.yaml" ]; then
        kubectl apply -f infra/security/spire-server-deployment.yaml
    else
        echo -e "${YELLOW}⚠️  SPIRE Server manifest not found, using default${NC}"
        # Создать базовый манифест
        cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: spire-server
  namespace: spire
spec:
  serviceName: spire-server
  replicas: 1
  selector:
    matchLabels:
      app: spire-server
  template:
    metadata:
      labels:
        app: spire-server
    spec:
      serviceAccountName: spire-server
      containers:
      - name: spire-server
        image: ghcr.io/spiffe/spire-server:latest
        args: ["-config", "/run/spire/config/server.conf"]
        ports:
        - containerPort: 8081
        volumeMounts:
        - name: spire-config
          mountPath: /run/spire/config
        - name: spire-data
          mountPath: /run/spire/data
      volumes:
      - name: spire-config
        configMap:
          name: spire-server-config
      - name: spire-data
        persistentVolumeClaim:
          claimName: spire-server-data
EOF
    fi
    
    # Создать Service
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: spire-server
  namespace: spire
spec:
  selector:
    app: spire-server
  ports:
  - port: 8081
    targetPort: 8081
EOF
    
    echo -e "${GREEN}✅ SPIRE Server deployed${NC}"
}

# Deploy SPIRE Agent
deploy_spire_agent() {
    echo ""
    echo "🤖 Deploying SPIRE Agent..."
    
    # Применить манифест
    if [ -f "infra/security/spire-agent-daemonset.yaml" ]; then
        kubectl apply -f infra/security/spire-agent-daemonset.yaml
    else
        echo -e "${YELLOW}⚠️  SPIRE Agent manifest not found, using default${NC}"
        # Создать базовый манифест
        cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: spire-agent
  namespace: spire
spec:
  selector:
    matchLabels:
      app: spire-agent
  template:
    metadata:
      labels:
        app: spire-agent
    spec:
      serviceAccountName: spire-agent
      hostNetwork: true
      containers:
      - name: spire-agent
        image: ghcr.io/spiffe/spire-agent:latest
        args: ["-config", "/run/spire/config/agent.conf"]
        volumeMounts:
        - name: spire-config
          mountPath: /run/spire/config
        - name: spire-socket
          mountPath: /run/spire/sockets
      volumes:
      - name: spire-config
        configMap:
          name: spire-agent-config
      - name: spire-socket
        hostPath:
          path: /run/spire/sockets
          type: DirectoryOrCreate
EOF
    fi
    
    echo -e "${GREEN}✅ SPIRE Agent deployed${NC}"
}

# Проверка статуса
check_status() {
    echo ""
    echo "📊 Checking deployment status..."
    
    echo ""
    echo "SPIRE Server:"
    kubectl get pods -n spire -l app=spire-server
    
    echo ""
    echo "SPIRE Agent:"
    kubectl get pods -n spire -l app=spire-agent
    
    echo ""
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Wait for pods to be ready: kubectl wait --for=condition=ready pod -l app=spire-server -n spire"
    echo "2. Check logs: kubectl logs -n spire -l app=spire-server"
    echo "3. Register workloads: See infra/security/README.md"
}

# Main
main() {
    check_dependencies
    create_namespace
    generate_ca
    deploy_spire_server
    deploy_spire_agent
    check_status
}

main "$@"

