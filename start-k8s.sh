#!/bin/bash
###############################################################################
# x0tta6bl4 Kubernetes Deployment Launcher
# Развертывает систему на Kubernetes кластере
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 x0tta6bl4 Kubernetes Deployment Launcher${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Проверка kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl не установлен!${NC}"
    echo "   Установите: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

echo -e "${GREEN}✅ kubectl установлен${NC}"
kubectl version --short | head -1

# Выбор режима
echo ""
echo -e "${BLUE}Выберите режим развертывания:${NC}"
echo "  1) Development (1 replica, low resources)"
echo "  2) Staging (2 replicas, medium resources)"
echo "  3) Production (3+ replicas, high availability)"
echo "  4) Local Kind cluster"
echo ""
read -p "Выбор (1-4): " MODE

case $MODE in
    1) 
        REPLICAS=1
        NAMESPACE="x0tta6bl4-dev"
        RESOURCES="--limits memory=256Mi,cpu=250m --requests memory=128Mi,cpu=100m"
        ENV="development"
        ;;
    2)
        REPLICAS=2
        NAMESPACE="x0tta6bl4-staging"
        RESOURCES="--limits memory=512Mi,cpu=500m --requests memory=256Mi,cpu=250m"
        ENV="staging"
        ;;
    3)
        REPLICAS=3
        NAMESPACE="x0tta6bl4-prod"
        RESOURCES="--limits memory=1Gi,cpu=1000m --requests memory=512Mi,cpu=500m"
        ENV="production"
        ;;
    4)
        echo -e "${BLUE}⏳ Создание Kind кластера...${NC}"
        if ! command -v kind &> /dev/null; then
            echo "Установка Kind..."
            go install sigs.k8s.io/kind@latest || brew install kind
        fi
        kind create cluster --name x0tta6bl4 --image kindest/node:v1.31.0
        echo -e "${GREEN}✅ Kind кластер создан${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Неверный выбор${NC}"
        exit 1
        ;;
esac

# Проверка текущего контекста
echo ""
echo -e "${BLUE}📋 Текущий контекст Kubernetes:${NC}"
CURRENT_CONTEXT=$(kubectl config current-context)
echo "  Context: $CURRENT_CONTEXT"

# Создание namespace
echo ""
echo -e "${BLUE}📦 Создание namespace: $NAMESPACE${NC}"
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

# Создание ConfigMap из .env
echo ""
echo -e "${BLUE}⚙️  Создание ConfigMap для конфигурации${NC}"

if [ -f ".env.$ENV" ]; then
    kubectl create configmap x0tta6bl4-config \
        --from-file=".env=$PWD/.env.$ENV" \
        -n "$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    echo -e "${GREEN}✅ ConfigMap создан из .env.$ENV${NC}"
else
    echo -e "${YELLOW}⚠️  .env.$ENV не найден, использую значения по умолчанию${NC}"
    kubectl create configmap x0tta6bl4-config \
        --from-literal="LOG_LEVEL=INFO" \
        --from-literal="ENVIRONMENT=$ENV" \
        -n "$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
fi

# Развертывание через kubectl
echo ""
echo -e "${BLUE}🚀 Развертывание приложения${NC}"

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: x0tta6bl4
  namespace: $NAMESPACE
  labels:
    app: x0tta6bl4
    version: "3.1.0"
spec:
  type: LoadBalancer
  ports:
    - name: api
      port: 8000
      targetPort: 8000
      protocol: TCP
    - name: metrics
      port: 9090
      targetPort: 9090
      protocol: TCP
  selector:
    app: x0tta6bl4
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: x0tta6bl4
  namespace: $NAMESPACE
  labels:
    app: x0tta6bl4
    version: "3.1.0"
spec:
  serviceName: x0tta6bl4
  replicas: $REPLICAS
  selector:
    matchLabels:
      app: x0tta6bl4
  template:
    metadata:
      labels:
        app: x0tta6bl4
        version: "3.1.0"
    spec:
      containers:
      - name: x0tta6bl4
        image: x0tta6bl4:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: api
        - containerPort: 9090
          name: metrics
        env:
        - name: LOG_LEVEL
          value: "INFO"
        - name: ENVIRONMENT
          value: "$ENV"
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
          requests:
            memory: "256Mi"
            cpu: "250m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: x0tta6bl4-config
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: x0tta6bl4-hpa
  namespace: $NAMESPACE
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: StatefulSet
    name: x0tta6bl4
  minReplicas: $REPLICAS
  maxReplicas: $((REPLICAS * 3))
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
EOF

# Ожидание развертывания
echo ""
echo -e "${BLUE}⏳ Ожидание развертывания${NC}"
kubectl rollout status statefulset/x0tta6bl4 -n "$NAMESPACE" --timeout=5m

# Информация о доступе
echo ""
echo -e "${GREEN}✅ Развертывание успешно!${NC}"
echo ""
echo -e "${BLUE}📊 Информация о сервисах:${NC}"
kubectl get svc -n "$NAMESPACE"

echo ""
echo -e "${BLUE}📈 Мониторинг подов:${NC}"
kubectl get pods -n "$NAMESPACE" -w &
sleep 3
kill %1 2>/dev/null || true

# Проверка здоровья
echo ""
echo -e "${BLUE}🏥 Проверка здоровья сервиса${NC}"
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')
echo "  Pod: $POD_NAME"

kubectl logs "$POD_NAME" -n "$NAMESPACE" --tail=5 2>/dev/null || echo "  Логи еще не доступны..."

# Команды для дальнейшей работы
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Полезные команды:${NC}"
echo ""
echo "  Логи:"
echo "    kubectl logs -n $NAMESPACE deployment/x0tta6bl4"
echo ""
echo "  Масштабирование:"
echo "    kubectl scale statefulset/x0tta6bl4 --replicas=5 -n $NAMESPACE"
echo ""
echo "  Проброс портов:"
echo "    kubectl port-forward -n $NAMESPACE svc/x0tta6bl4 8000:8000"
echo ""
echo "  Удаление:"
echo "    kubectl delete namespace $NAMESPACE"
echo ""
echo -e "${YELLOW}API будет доступен на: http://localhost:8000${NC}"
echo -e "${YELLOW}Метрики на: http://localhost:9090${NC}"
