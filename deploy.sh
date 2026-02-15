#!/bin/bash
# deploy.sh --mode [production|development] --target [local|vps:IP] --components [mesh,dao,vpn] --vault-token <token> --vault-addr <addr> --dry-run

# --- Конфигурация и утилиты ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO] $1${NC}"; }
log_warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
log_error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }

# --- Парсинг аргументов ---
MODE=""
TARGET=""
COMPONENTS=""
VAULT_TOKEN=""
VAULT_ADDR=""
DRY_RUN=false

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --mode) MODE="$2"; shift ;;
        --target) TARGET="$2"; shift ;;
        --components) COMPONENTS="$2"; shift ;;
        --vault-token) VAULT_TOKEN="$2"; shift ;;
        --vault-addr) VAULT_ADDR="$2"; shift ;;
        --dry-run) DRY_RUN=true ;;
        *) log_error "Неизвестный аргумент: $1" ;;
    esac
    shift
done

if [ -z "$MODE" ] || [ -z "$TARGET" ] || [ -z "$COMPONENTS" ]; then
    log_error "Использование: $0 --mode [production|development] --target [local|vps:IP] --components [mesh,dao,vpn] [--vault-token <token>] [--vault-addr <addr>] [--dry-run]"
fi

log_info "Режим: $MODE"
log_info "Цель: $TARGET"
log_info "Компоненты: $COMPONENTS"
if [ "$DRY_RUN" = true ]; then log_warn "ВКЛЮЧЕН РЕЖИМ DRY-RUN"; fi

# Определяем, используем ли mock Vault для разработки
if [ "$VAULT_DEV_MODE" = "true" ]; then
    log_warn "АКТИВИРОВАН РЕЖИМ РАЗРАБОТКИ С MOCK VAULT!"
    VAULT_ADDR="http://mock-vault:8200" # Устанавливаем фиктивный адрес Vault
    VAULT_TOKEN="mock-token" # Устанавливаем фиктивный токен
    export VAULT_DEV_MODE="true"
    export VAULT_SECRETS_DIR="${VAULT_SECRETS_DIR:-/tmp/x0tta6bl4-secrets}"
    log_info "Мок-секреты будут храниться в: $VAULT_SECRETS_DIR"
    check_cmd "bash" # Убедимся, что bash доступен для mock-скрипта
    if [ ! -x "./scripts/mock-vault-dev.sh" ]; then
        log_error "Скрипт mock-vault-dev.sh не найден или не исполняем. Убедитесь, что он существует и имеет права x."
    fi
fi

# --- 1. Preflight checks (Vault, Docker, K8s, сертификаты) ---
log_info "Выполнение предварительных проверок..."

check_cmd() {
    local cmd=$1
    if [ "$VAULT_DEV_MODE" = "true" ]; then
        # В режиме разработки Vault, oqs_apps, curl не нужны
        if [[ "$cmd" == "vault" || "$cmd" == "oqs_apps" || "$cmd" == "curl" ]]; then
            log_info "Проверка команды $cmd пропущена в DEV режиме."
            return
        fi
    fi
    
    if ! command -v "$cmd" &> /dev/null; then
        log_error "Не найдена команда: $cmd. Пожалуйста, установите ее."
    fi
}

check_cmd "vault"
check_cmd "docker"
check_cmd "kubectl"
check_cmd "ssh"
check_cmd "wg" # WireGuard CLI
check_cmd "jq" # Для парсинга JSON из Vault
check_cmd "oqs_apps" # Для генерации PQC ключей
check_cmd "curl" # Для vault_get

log_info "Все необходимые команды найдены."

# --- 2. Secrets injection из Vault ---
log_info "Инъекция секретов из Vault..."

if [ -z "$VAULT_TOKEN" ] && [ "$VAULT_DEV_MODE" != "true" ]; then # Только ошибка, если не dev mode
    log_error "Для инъекции секретов из Vault необходимы --vault-token и --vault-addr."
fi
if [ -z "$VAULT_ADDR" ] && [ "$VAULT_DEV_MODE" != "true" ]; then # Только ошибка, если не dev mode
    log_error "Для инъекции секретов из Vault необходимы --vault-token и --vault-addr."
fi

export VAULT_ADDR # Экспортируем для vault CLI

# Функция vault_get, предоставленная в промпте
vault_get() {
    local path=$1
    local field=$2
    if [ -z "$VAULT_TOKEN" ] && [ "$VAULT_DEV_MODE" != "true" ]; then
        log_error "VAULT_TOKEN не задан. Используйте --vault-token"
    fi
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY-RUN: vault_get $path $field -> DUMMY_SECRET_VALUE"
        echo "DUMMY_SECRET_VALUE"
        return
    fi
    if [ "$VAULT_DEV_MODE" = "true" ]; then
        # Call mock script if in dev mode
        log_info "Использование mock-Vault для получения секрета: $path/$field"
        bash scripts/mock-vault-dev.sh kv get -field="$field" "$path" || log_error "Ошибка получения секрета из mock-Vault: $path/$field"
    else
        # Call real Vault CLI via curl
        curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
             "$VAULT_ADDR/v1/secret/data/$path" | jq -r ".data.data.$field" || log_error "Ошибка получения секрета из Vault: $path/$field"
    fi
}

# Пример использования vault_get
# Секреты для deploy_mesh.sh
export X0TTA6BL4_NODE1_PASSWORD=$(vault_get "x0tta6bl4/mesh/node1" "root_password")
export X0TTA6BL4_NODE2_PASSWORD=$(vault_get "x0tta6bl4/mesh/node2" "root_password")
export X0TTA6BL4_NODE1_IP=$(vault_get "x0tta6bl4/mesh/node1" "ip_address")
export X0TTA6BL4_NODE2_IP=$(vault_get "x0tta6bl4/mesh/node2" "ip_address")

# Секреты для scripts/provision-grafana.sh
export GRAFANA_ADMIN_USER=$(vault_get "x0tta6bl4/monitoring" "admin_username")
export GRAFANA_ADMIN_PASSWORD=$(vault_get "x0tta6bl4/monitoring" "admin_password")

# Секреты для scripts/start_minio_server.sh (если файл существует)
export MINIO_ACCESS_KEY=$(vault_get "x0tta6bl4/minio" "access_key")
export MINIO_SECRET_KEY=$(vault_get "x0tta6bl4/minio" "secret_key")

# Убеждаемся, что секреты Postgres для K8s существуют в Vault
log_info "Убеждаемся, что секреты Postgres для K8s существуют в Vault..."
if [ "$DRY_RUN" = false ]; then
    if [ "$VAULT_DEV_MODE" = "true" ]; then
        log_warn "DEV-MODE: Проверка наличия секретов Postgres в Mock Vault."
        # Для mock-Vault просто проверяем, что mock-скрипт не возвращает ошибку
        bash scripts/mock-vault-dev.sh kv get -field="POSTGRES_PASSWORD" "secret/x0tta6bl4/postgres" > /dev/null || \
            log_error "Секреты Postgres для K8s (secret/x0tta6bl4/postgres) не найдены в Mock Vault."
    else
        VAULT_TOKEN="$VAULT_TOKEN" vault kv get secret/x0tta6bl4/postgres > /dev/null 2>&1 || \
            log_error "Секреты Postgres для K8s (secret/x0tta6bl4/postgres) не найдены в Vault."
    fi
fi


# --- 3. Post-quantum ключей генерация (если новый узел) ---
log_info "Генерация Post-quantum ключей..."
KYBER_SK_PATH="/etc/x0tta6bl4/kyber.key"
KYBER_PK_PATH="/etc/x0tta6bl4/kyber.pub"

if [ "$DRY_RUN" = true ]; then
    log_warn "DRY-RUN: Генерация PQC ключей пропущена."
elif [ ! -f "$KYBER_SK_PATH" ]; then
    log_info "PQC ключи Kyber не найдены. Генерируем новые..."
    mkdir -p "$(dirname "$KYBER_SK_PATH")"
    python3 -c "from src.security.post_quantum import LibOQSBackend; \
                pqc_backend = LibOQSBackend(); \
                keypair = pqc_backend.generate_kem_keypair(); \
                open('$KYBER_PK_PATH', 'wb').write(keypair.public_key); \
                open('$KYBER_SK_PATH', 'wb').write(keypair.private_key)"
    log_warn "TODO: Реализовать сохранение приватных PQC ключей в Vault вместо локального хранения."
    log_info "PQC ключи Kyber сгенерированы и сохранены локально."
else
    log_info "PQC ключи Kyber уже существуют. Пропускаем генерацию."
fi


# --- 4. Mesh topology автоконфигурация ---
log_info "Автоконфигурация Mesh topology..."
if [[ "$COMPONENTS" == *"mesh"* ]]; then
    log_info "Настройка mesh-топологии..."
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY-RUN: Запуск src.network.mesh_bootstrap"
    else
        python3 -m src.network.mesh_bootstrap \
            --mode "$MODE" \
            --peers "$(vault_get 'x0tta6bl4/mesh' 'peer_list')"
    fi
fi


# --- 5. MAPE-K циклов инициализация ---
log_info "Инициализация MAPE-K циклов..."
if [ "$MODE" == "production" ]; then
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY-RUN: Применение infra/kubernetes/mape-k-deployment.yaml и ожидание готовности."
    else
        log_info "Применение infra/kubernetes/mape-k-deployment.yaml..."
        kubectl apply -f infra/kubernetes/mape-k-deployment.yaml || log_error "Не удалось применить MAPE-K deployment."
        log_info "Ожидание готовности подов MAPE-K..."
        kubectl wait --for=condition=ready pod -l app=mape-k --timeout=60s || log_error "Поды MAPE-K не перешли в состояние готовности."
    fi
fi


# --- 6. Health checks + rollback при сбое ---
log_info "Выполнение health checks..."
if [ "$DRY_RUN" = true ]; then
    log_warn "DRY-RUN: Выполнение health checks и логики отката."
else
    if ! python3 -m src.health.check_mesh --timeout 30; then
        log_error "Health check провален. Инициируем откат..."
        if [ "$DRY_RUN" = false ]; then
            kubectl rollout undo deployment/mesh-node || log_error "Откат не удался."
        fi
        exit 1
    fi
    log_info "Health check пройден успешно."
fi


# --- 7. DAO-регистрация узла + IPFS snapshot ---
log_info "DAO-регистрация узла и IPFS snapshot..."
if [[ "$COMPONENTS" == *"dao"* ]]; then
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY-RUN: Вызов скрипта DAO-регистрации."
        log_warn "DRY-RUN: Создание IPFS snapshot."
    else
        log_info "Регистрация узла в DAO..."
        NODE_ID=$(python3 -c "from src.dao.register import register_node; print(register_node())")
        log_info "Узел зарегистрирован: $NODE_ID"
        
        log_info "Создание IPFS snapshot..."
        # Предполагаем, что IPFS CLI установлен и настроен
        ipfs add -r /etc/x0tta6bl4/state/ | tee /tmp/ipfs_snapshot.log || log_warn "Не удалось создать IPFS snapshot."
    fi
fi

log_info "Развертывание завершено (шаблон)."
