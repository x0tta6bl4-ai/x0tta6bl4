#!/bin/bash
# Setup External Access for Beta Customer
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

# Check if ingress controller is available
check_ingress_controller() {
    log "Проверка ingress controller..."
    
    if kubectl get ingressclass 2>/dev/null | grep -q nginx; then
        log "✅ Nginx ingress controller найден"
        return 0
    fi
    
    warn "Ingress controller не найден. Используем port-forward как альтернативу."
    return 1
}

# Setup port-forward as alternative
setup_port_forward() {
    log "Настройка port-forward для доступа..."
    
    local port="${2:-8080}"
    local local_port="${3:-8080}"
    
    info "Port-forward будет доступен на: http://localhost:${local_port}"
    info "Запусти в отдельном терминале:"
    info "  kubectl port-forward -n ${NAMESPACE} svc/x0tta6bl4-staging ${local_port}:${port}"
    
    # Create helper script
    mkdir -p "beta-customers/${CUSTOMER_NAME}"
    cat > "beta-customers/${CUSTOMER_NAME}/port-forward.sh" <<EOF
#!/bin/bash
# Port-forward для доступа к x0tta6bl4-staging
# Запусти этот скрипт для доступа к сервису

kubectl port-forward -n ${NAMESPACE} svc/x0tta6bl4-staging ${local_port}:${port} &
echo "Port-forward запущен. Доступ: http://localhost:${local_port}"
echo "Нажми Ctrl+C для остановки"
wait
EOF
    chmod +x "beta-customers/${CUSTOMER_NAME}/port-forward.sh"
    
    log "✅ Port-forward script создан"
}

# Setup ingress (if controller available)
setup_ingress() {
    log "Настройка ingress для внешнего доступа..."
    
    if [ -f "k8s/ingress-beta-customer.yaml" ]; then
        kubectl apply -f k8s/ingress-beta-customer.yaml || {
            warn "Не удалось применить ingress. Проверь конфигурацию."
            return 1
        }
        
        log "✅ Ingress создан"
        
        # Get ingress IP/hostname
        sleep 5
        local ingress_info=$(kubectl get ingress -n "$NAMESPACE" x0tta6bl4-staging-beta -o jsonpath='{.status.loadBalancer.ingress[0].hostname}{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
        
        if [ -n "$ingress_info" ]; then
            info "Ingress доступен на: $ingress_info"
            echo "$ingress_info" > "beta-customers/${CUSTOMER_NAME}/ingress_url.txt"
        else
            warn "Ingress IP/hostname еще не назначен. Проверь позже."
        fi
        
        return 0
    else
        warn "Ingress конфигурация не найдена"
        return 1
    fi
}

# Create access instructions
create_access_instructions() {
    log "Создание инструкций по доступу..."
    
    local access_file="beta-customers/${CUSTOMER_NAME}/КАК_ПОДКЛЮЧИТЬСЯ.md"
    
    cat > "$access_file" <<'ACCESSEOF'
# Как подключиться к x0tta6bl4

## Вариант 1: Port-forward (если нет внешнего доступа)

Запусти скрипт:
```bash
./port-forward.sh
```

Или вручную:
```bash
kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080
```

После этого сервис будет доступен на: http://localhost:8080

## Вариант 2: Ingress (если настроен)

Проверь файл `ingress_url.txt` для получения URL.

Или проверь сам:
```bash
kubectl get ingress -n x0tta6bl4-staging x0tta6bl4-staging-beta
```

## Вариант 3: Прямой доступ к кластеру

Если у тебя есть доступ к кластеру:
```bash
curl http://x0tta6bl4-staging.x0tta6bl4-staging.svc.cluster.local:8080/health
```

## Проверка доступа

После настройки доступа проверь:
```bash
curl http://[your-endpoint]/health
```

Должен вернуться `{"status":"ok"}`.

## Если не работает

1. Проверь, что pods запущены:
   ```bash
   kubectl get pods -n x0tta6bl4-staging
   ```

2. Проверь, что service работает:
   ```bash
   kubectl get svc -n x0tta6bl4-staging
   ```

3. Напиши нам:
   - Telegram: @x0tta6bl4_allert_bot
   - Email: support@x0tta6bl4.com
ACCESSEOF

    log "✅ Инструкции по доступу созданы"
}

# Update customer config with access info
update_customer_config() {
    log "Обновление конфигурации customer с информацией о доступе..."
    
    local config_file="beta-customers/${CUSTOMER_NAME}/config.yaml"
    
    if [ -f "$config_file" ]; then
        # Add access methods
        cat >> "$config_file" <<EOF

# Access Methods
access_methods:
  port_forward:
    command: "kubectl port-forward -n x0tta6bl4-staging svc/x0tta6bl4-staging 8080:8080"
    url: "http://localhost:8080"
  ingress:
    url: "$(cat beta-customers/${CUSTOMER_NAME}/ingress_url.txt 2>/dev/null || echo 'Not configured')"
  internal:
    url: "http://x0tta6bl4-staging.x0tta6bl4-staging.svc.cluster.local:8080"
EOF
        log "✅ Конфигурация обновлена"
    fi
}

# Main
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Настройка доступа для Beta Customer                       ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    if check_ingress_controller; then
        setup_ingress || setup_port_forward "$@"
    else
        setup_port_forward "$@"
    fi
    
    create_access_instructions
    update_customer_config
    
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     ✅ Настройка доступа завершена                            ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    log "📄 Инструкции: beta-customers/${CUSTOMER_NAME}/КАК_ПОДКЛЮЧИТЬСЯ.md"
    log "📄 Port-forward script: beta-customers/${CUSTOMER_NAME}/port-forward.sh"
}

main "$@"


