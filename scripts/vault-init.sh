#!/bin/bash
# scripts/vault-init.sh
# Инициализация Vault секретами, необходимыми для развертывания x0tta6bl4.

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO] $1${NC}"; }
log_warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
log_error() { echo -e "${RED}[ERROR] $1${NC}"; exit 1; }

# --- Парсинг аргументов ---
CLUSTER_NAME=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --cluster) CLUSTER_NAME="$2"; shift ;;
        *) log_error "Неизвестный аргумент: $1" ;;
    esac
    shift
done

if [ -z "$CLUSTER_NAME" ]; then
    log_error "Использование: $0 --cluster [production|development|...]"
fi

log_info "🚀 Инициализация секретов Vault для кластера: $CLUSTER_NAME..."

# Проверка наличия Vault CLI и токена
check_vault_status() {
    if ! command -v vault &> /dev/null; then
        log_error "Vault CLI не найдена. Пожалуйста, установите ее."
    fi
    if [ -z "$VAULT_ADDR" ]; then
        log_error "VAULT_ADDR не задан. Убедитесь, что переменная окружения VAULT_ADDR установлена."
    fi
    if [ -z "$VAULT_TOKEN" ]; then
        log_error "VAULT_TOKEN не задан. Убедитесь, что переменная окружения VAULT_TOKEN установлена."
    fi
    log_info "Vault CLI и переменные окружения доступны."
}
check_vault_status

# --- Инициализация PQC секретов (Kyber) ---
log_info "Инициализация PQC секретов (Kyber)..."
# Генерируем новые PQC ключи для примера, в production они должны быть сгенерированы безопасно.
PQC_KEYS_DIR="/tmp/x0tta6bl4-pqc-init-keys"
mkdir -p "$PQC_KEYS_DIR"
oqs_apps genkey Kyber768 > "$PQC_KEYS_DIR/kyber.key"
oqs_apps pubkey Kyber768 < "$PQC_KEYS_DIR/kyber.key" > "$PQC_KEYS_DIR/kyber.pub"

# Сохраняем ключи в Vault
log_info "Сохранение PQC Kyber ключей в Vault..."
vault kv put "secret/x0tta6bl4/pqc/global" 
    kyber_public_key=@"$PQC_KEYS_DIR/kyber.pub" 
    kyber_private_key=@"$PQC_KEYS_DIR/kyber.key" || log_error "Не удалось сохранить PQC Kyber ключи в Vault."
rm -rf "$PQC_KEYS_DIR" # Удаляем временные файлы

# --- Инициализация секретов mesh-сети ---
log_info "Инициализация секретов mesh-сети..."
# Эти значения должны быть заменены реальными production-секретами
vault kv put "secret/x0tta6bl4/mesh/node1" 
    root_password="<GENERATE_STRONG_PASSWORD_1>" 
    ip_address="root@89.125.1.107" || log_error "Не удалось сохранить секреты Node 1 в Vault."
vault kv put "secret/x0tta6bl4/mesh/node2" 
    root_password="<GENERATE_STRONG_PASSWORD_2>" 
    ip_address="root@77.83.245.27" || log_error "Не удалось сохранить секреты Node 2 в Vault."
vault kv put "secret/x0tta6bl4/mesh" 
    peer_list="root@89.125.1.107,root@77.83.245.27" || log_error "Не удалось сохранить список пиров в Vault."


# --- Инициализация секретов мониторинга (Grafana) ---
log_info "Инициализация секретов мониторинга (Grafana)..."
vault kv put "secret/x0tta6bl4/monitoring" 
    admin_username="admin" 
    admin_password="<GENERATE_STRONG_GRAFANA_PASSWORD>" || log_error "Не удалось сохранить секреты Grafana в Vault."

# --- Инициализация секретов Minio ---
log_info "Инициализация секретов Minio..."
vault kv put "secret/x0tta6bl4/minio" 
    access_key="<GENERATE_MINIO_ACCESS_KEY>" 
    secret_key="<GENERATE_MINIO_SECRET_KEY>" || log_error "Не удалось сохранить секреты Minio в Vault."

# --- Инициализация секретов Postgres для K8s ---
log_info "Инициализация секретов Postgres для K8s..."
# Эти секреты будут использоваться Kubernetes для создания Secret
vault kv put "secret/x0tta6bl4/postgres" 
    POSTGRES_PASSWORD="<GENERATE_STRONG_POSTGRES_PASSWORD>" 
    POSTGRES_ADMIN_PASSWORD="<GENERATE_STRONG_POSTGRES_ADMIN_PASSWORD>" 
    POSTGRES_APP_PASSWORD="<GENERATE_STRONG_POSTGRES_APP_PASSWORD>" 
    POSTGRES_REPLICATION_PASSWORD="<GENERATE_STRONG_POSTGRES_REPLICATION_PASSWORD>" || log_error "Не удалось сохранить секреты Postgres в Vault."

log_info "✅ Инициализация секретов Vault для кластера $CLUSTER_NAME завершена."
log_warn "НЕ ЗАБУДЬТЕ ЗАМЕНИТЬ ПЛЕЙСХОЛДЕРЫ <GENERATE_STRONG_PASSWORD_*> РЕАЛЬНЫМИ СЕКРЕТАМИ!"
