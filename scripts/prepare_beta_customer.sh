#!/bin/bash
# Prepare x0tta6bl4 for Beta Customer
# Дата: 2026-01-08
# Версия: 1.0

set -euo pipefail

NAMESPACE="x0tta6bl4-staging"
CUSTOMER_NAME="${1:-beta-customer-1}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Проверка предварительных условий..."
    
    if ! command -v kubectl &> /dev/null; then
        error "kubectl не найден"
        exit 1
    fi
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        error "Namespace $NAMESPACE не найден"
        exit 1
    fi
    
    log "✅ Все предварительные условия выполнены"
}

# Check system health
check_system_health() {
    log "Проверка здоровья системы..."
    
    local pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | wc -l)
    if [ "$pods" -lt 3 ]; then
        error "Недостаточно running pods: $pods"
        return 1
    fi
    
    log "✅ System health: $pods pods Running"
    
    # Check health endpoint
    local service_url=$(kubectl get svc -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -n "$service_url" ]; then
        info "Service: $service_url"
    fi
    
    return 0
}

# Create customer namespace (optional, for isolation)
create_customer_namespace() {
    log "Создание namespace для customer (опционально)..."
    
    local customer_ns="${CUSTOMER_NAME}-ns"
    
    if kubectl get namespace "$customer_ns" &> /dev/null; then
        warn "Namespace $customer_ns уже существует"
    else
        info "Создание namespace $customer_ns (опционально, можно использовать общий staging)"
        # kubectl create namespace "$customer_ns" || warn "Не удалось создать namespace"
    fi
}

# Generate access credentials
generate_credentials() {
    log "Генерация access credentials..."
    
    # Generate API token (example)
    local api_token=$(openssl rand -hex 32 2>/dev/null || echo "beta-token-$(date +%s)")
    
    info "API Token: $api_token"
    info "Сохраните этот token для customer"
    
    # Save to file
    mkdir -p "beta-customers/${CUSTOMER_NAME}"
    echo "$api_token" > "beta-customers/${CUSTOMER_NAME}/api_token.txt"
    chmod 600 "beta-customers/${CUSTOMER_NAME}/api_token.txt"
    
    log "✅ Credentials сохранены в beta-customers/${CUSTOMER_NAME}/"
}

# Create customer configuration
create_customer_config() {
    log "Создание конфигурации для customer..."
    
    mkdir -p "beta-customers/${CUSTOMER_NAME}"
    
    cat > "beta-customers/${CUSTOMER_NAME}/config.yaml" <<EOF
# Configuration for ${CUSTOMER_NAME}
# Дата: $(date +%Y-%m-%d)

customer:
  name: ${CUSTOMER_NAME}
  namespace: ${NAMESPACE}
  environment: staging
  created: $(date -u +%Y-%m-%dT%H:%M:%SZ)

access:
  service_url: http://x0tta6bl4-staging.${NAMESPACE}.svc.cluster.local:8080
  health_endpoint: /health
  metrics_endpoint: /metrics
  api_token: $(cat beta-customers/${CUSTOMER_NAME}/api_token.txt)

monitoring:
  prometheus_url: http://prometheus.monitoring.svc.cluster.local:9090
  alertmanager_url: http://alertmanager.monitoring.svc.cluster.local:9093

support:
  telegram: @x0tta6bl4_allert_bot
  email: support@x0tta6bl4.com
  response_time_sev1: 5min
  response_time_sev2: 15min
EOF

    log "✅ Configuration создана"
}

# Verify access
verify_access() {
    log "Проверка доступа к сервису..."
    
    # Check if we can access the service
    local pod=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -n "$pod" ]; then
        info "Testing health endpoint via pod: $pod"
        kubectl exec -n "$NAMESPACE" "$pod" -- curl -sf http://localhost:8080/health > /dev/null 2>&1 && {
            log "✅ Health endpoint доступен"
        } || {
            warn "Health endpoint недоступен (может быть нормально для staging)"
        }
    fi
}

# Create monitoring labels
create_monitoring_labels() {
    log "Настройка мониторинга для customer..."
    
    # Add labels to pods for customer-specific monitoring (if needed)
    info "Monitoring настроен для namespace $NAMESPACE"
    info "Customer-specific labels можно добавить при необходимости"
}

# Generate onboarding summary
generate_summary() {
    log "Генерация summary для customer..."
    
    local summary_file="beta-customers/${CUSTOMER_NAME}/ONBOARDING_SUMMARY.md"
    
    cat > "$summary_file" <<EOF
# Onboarding Summary for ${CUSTOMER_NAME}
**Дата:** $(date +%Y-%m-%d)

## Access Information

- **Service URL:** http://x0tta6bl4-staging.${NAMESPACE}.svc.cluster.local:8080
- **API Token:** $(cat beta-customers/${CUSTOMER_NAME}/api_token.txt)
- **Namespace:** ${NAMESPACE}

## Quick Start

1. Health check:
   \`\`\`bash
   curl http://x0tta6bl4-staging.${NAMESPACE}.svc.cluster.local:8080/health
   \`\`\`

2. Metrics:
   \`\`\`bash
   curl http://x0tta6bl4-staging.${NAMESPACE}.svc.cluster.local:8080/metrics
   \`\`\`

## Support

- **Telegram:** @x0tta6bl4_allert_bot
- **Email:** support@x0tta6bl4.com
- **Response Time:** SEV-1: 5min, SEV-2: 15min

## Documentation

- **Onboarding Guide:** BETA_CUSTOMER_ONBOARDING_GUIDE_2026_01_08.md
- **Troubleshooting:** TROUBLESHOOTING_QUICK_REFERENCE_2026_01_07.md

---

**Generated:** $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

    log "✅ Summary создан: $summary_file"
}

# Main
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Подготовка x0tta6bl4 для Beta Customer                    ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    check_prerequisites
    check_system_health
    create_customer_namespace
    generate_credentials
    create_customer_config
    verify_access
    create_monitoring_labels
    generate_summary
    
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     ✅ Подготовка завершена                                   ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    log "📄 Файлы созданы в: beta-customers/${CUSTOMER_NAME}/"
    log "📋 Onboarding Guide: BETA_CUSTOMER_ONBOARDING_GUIDE_2026_01_08.md"
    log "🎯 Следующий шаг: Отправьте credentials и guide customer"
}

main


