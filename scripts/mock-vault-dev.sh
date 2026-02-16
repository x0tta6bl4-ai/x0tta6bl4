#!/bin/bash
# scripts/mock-vault-dev.sh
# Мок-скрипт для имитации Vault CLI в режиме разработки.
# Предназначен для использования, когда реальный Vault недоступен или не нужен.

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO] Mock-Vault: $1${NC}"; }
log_warn() { echo -e "${YELLOW}[WARN] Mock-Vault: $1${NC}"; }
log_error() { echo -e "${RED}[ERROR] Mock-Vault: $1${NC}"; exit 1; }

# Проверяем, что включен режим разработки
if [ "$VAULT_DEV_MODE" != "true" ]; then
    log_error "Режим mock-Vault может быть использован только с VAULT_DEV_MODE=true."
fi

# Проверяем директорию для хранения мок-секретов
if [ -z "$VAULT_SECRETS_DIR" ]; then
    log_error "Переменная окружения VAULT_SECRETS_DIR не задана. Укажите директорию для мок-секретов."
fi
mkdir -p "$VAULT_SECRETS_DIR" || log_error "Не удалось создать директорию для мок-секретов: $VAULT_SECRETS_DIR"

# --- Реализация мок-команд ---
case "$1" in
    "kv")
        case "$2" in
            "get")
                local field_flag=""
                local path=""
                
                # Парсинг флагов
                for ((i=3; i<=$#; i++)); do
                    arg="${!i}"
                    if [[ "$arg" == "-field="* ]]; then
                        field_flag="${arg#*=}"
                    elif [[ "$arg" != "-"* ]]; then # Предполагаем, что это путь
                        path="$arg"
                    fi
                done

                if [ -z "$path" ]; then
                    log_error "Не указан путь для 'vault kv get'."
                fi
                if [ -z "$field_flag" ]; then
                    log_error "Не указано поле для 'vault kv get'. Используйте -field=<key>."
                fi

                # Очищаем путь для формирования имени файла
                local cleaned_path=$(echo "$path" | sed 's/secret\/data\///g' | tr '/' '_')
                local secret_file="${VAULT_SECRETS_DIR}/${cleaned_path}_${field_flag}.mock"

                if [ -f "$secret_file" ]; then
                    cat "$secret_file"
                else
                    log_warn "Мок-секрет не найден для пути '$path', поле '$field_flag'."
                    exit 1 # Возвращаем ошибку, как реальный Vault
                fi
            ;;
            "put")
                local path=""
                local secrets_to_put=()

                # Парсинг флагов и секретов
                for ((i=3; i<=$#; i++)); do
                    arg="${!i}"
                    if [[ "$arg" != "-"* ]]; then # Это путь или пара key=value
                        if [ -z "$path" ]; then
                            path="$arg"
                        else
                            secrets_to_put+=("$arg")
                        fi
                    fi
                done
                
                if [ -z "$path" ]; then
                    log_error "Не указан путь для 'vault kv put'."
                fi
                if [ ${#secrets_to_put[@]} -eq 0 ]; then
                    log_error "Не указаны секреты для 'vault kv put'."
                fi

                # Сохраняем каждый секрет в отдельный файл
                local cleaned_path=$(echo "$path" | sed 's/secret\/data\///g' | tr '/' '_')
                for secret_pair in "${secrets_to_put[@]}"; do
                    local key=$(echo "$secret_pair" | cut -d'=' -f1)
                    local value=$(echo "$secret_pair" | cut -d'=' -f2-)
                    local secret_file="${VAULT_SECRETS_DIR}/${cleaned_path}_${key}.mock"
                    echo "$value" > "$secret_file"
                    log_info "Сохранен мок-секрет: '$key' в '$secret_file'."
                done
                log_info "Мок-секреты сохранены для пути '$path'."
            ;;
            *)
                log_error "Неизвестная команда kv: $2"
            ;;
        esac
    ;;
    "secrets")
        # Имитируем включение secrets engine
        case "$2" in
            "enable")
                log_info "Мок: Secrets engine $3 включен."
            ;;
            *)
                log_error "Неизвестная команда secrets: $2"
            ;;
        esac
    ;;
    *)
        log_error "Неизвестная команда Vault: $1"
    ;;
esac
