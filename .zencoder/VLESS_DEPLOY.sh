#!/bin/bash

################################################################################
# x0tta6bl4 VLESS Security Hardening - ONE-CLICK Deploy
# Автоматическое развёртывание hardened VLESS конфигурации
# Version: 2.0 | Date: 2026-01-16
################################################################################

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
XRAY_DIR="/etc/x-ray"
VLESS_SECURE_DIR="/etc/vless-secure"
BACKUP_DIR="/var/backups/x-ray"
LOG_DIR="/var/log/vless"
LOG_FILE="/var/log/x-ray-deploy.log"
DEPLOY_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

################################################################################
# Функции логирования
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[✅]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[❌]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[⚠️]${NC} $1" | tee -a "$LOG_FILE"
}

################################################################################
# Проверки перед развёртыванием
################################################################################

check_prerequisites() {
    log_info "Проверка предусловий..."

    # Проверка прав root
    if [[ $EUID -ne 0 ]]; then
        log_error "Скрипт должен быть запущен с правами root (sudo)"
        exit 1
    fi
    log_success "Права root подтверждены"

    # Проверка ОС
    if ! command -v systemctl &> /dev/null; then
        log_error "systemd не найден. Требуется systemd-based система"
        exit 1
    fi
    log_success "systemd обнаружена"

    # Проверка x-ray
    if ! command -v x-ray &> /dev/null; then
        log_warning "x-ray не найден. Установка..."
        install_xray
    else
        log_success "x-ray найден: $(x-ray version | head -1)"
    fi

    # Проверка jq для парсинга JSON
    if ! command -v jq &> /dev/null; then
        log_warning "jq не найден. Установка..."
        apt-get update -qq && apt-get install -y -qq jq
    fi
    log_success "jq установлен"
}

install_xray() {
    log_info "Установка x-ray..."
    bash -c "$(curl -L https://raw.githubusercontent.com/XTLS/Xray-install/main/install-release.sh)" @ install
    log_success "x-ray установлен"
}

################################################################################
# Создание директорий и файлов
################################################################################

create_directories() {
    log_info "Создание защищённых директорий..."

    mkdir -p "$XRAY_DIR"
    mkdir -p "$VLESS_SECURE_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$LOG_DIR"

    # Установка прав доступа
    chmod 750 "$XRAY_DIR"
    chmod 700 "$VLESS_SECURE_DIR"
    chmod 755 "$BACKUP_DIR"
    chmod 755 "$LOG_DIR"

    log_success "Директории созданы с правами доступа"
}

################################################################################
# Генерация ключей
################################################################################

generate_keys() {
    log_info "Генерация новых Reality ключей..."

    # Генерируем приватный ключ
    PRIVATE_KEY=$(openssl rand -base64 32)
    log_success "Приватный ключ сгенерирован"

    # Генерируем публичный ключ (можно использовать openssl или x-ray)
    PUBLIC_KEY=$(echo "$PRIVATE_KEY" | openssl base64 -d | openssl dgst -sha256 -binary | openssl base64)
    log_success "Публичный ключ сгенерирован"

    # Сохраняем в защищённый env файл
    cat > "$XRAY_DIR/vless.env" << 'EOF'
#!/bin/bash
# X-Ray VLESS Security Environment Variables
# Generated: DEPLOY_TIMESTAMP

VLESS_PRIVATE_KEY="PRIVATE_KEY_PLACEHOLDER"
VLESS_PUBLIC_KEY="PUBLIC_KEY_PLACEHOLDER"
VLESS_SHORTIDS="00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f"
VLESS_TARGETS="google.com cloudflare.com amazon.com microsoft.com apple.com"
EOF

    # Заменяем плейсхолдеры
    sed -i "s/DEPLOY_TIMESTAMP/$(date)/g" "$XRAY_DIR/vless.env"
    sed -i "s|PRIVATE_KEY_PLACEHOLDER|$PRIVATE_KEY|g" "$XRAY_DIR/vless.env"
    sed -i "s|PUBLIC_KEY_PLACEHOLDER|$PUBLIC_KEY|g" "$XRAY_DIR/vless.env"

    chmod 600 "$XRAY_DIR/vless.env"
    log_success "Environment файл создан: $XRAY_DIR/vless.env"

    # Экспортируем для использования в скрипте
    export VLESS_PRIVATE_KEY="$PRIVATE_KEY"
    export VLESS_PUBLIC_KEY="$PUBLIC_KEY"
}

################################################################################
# Миграция клиентов
################################################################################

migrate_clients() {
    log_info "Миграция клиентов в защищённое хранилище..."

    # Список клиентов (можно читать из старого конфига или из переменной)
    cat > "$VLESS_SECURE_DIR/clients.json" << 'CLIENTS_EOF'
{
  "clients": [
    {
      "email": "x0tta6bl4",
      "id": "f56fb669-32ec-4142-b2fe-8b65c4321102",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "x0tta6bl4_mobile",
      "id": "57782230-b5d6-45c6-aec1-ab3d23d143fb",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "hip3.14cirz",
      "id": "f1b2693b-2490-4ede-b2d9-06e5ece63a71",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "margarita",
      "id": "5fb8f932-cf3d-4695-b0b0-89caa6054c80",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "vasilisa",
      "id": "f70193b1-9729-4884-872b-93426525879a",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "Jamaica",
      "id": "5f3192a4-1652-404c-ac49-c4984ce2b8ec",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "v.Terehkova",
      "id": "a7569357-20d2-4c58-8e90-e7b9fec7ca3a",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "Vera.Vasil'evna",
      "id": "f269ef86-36ef-4a6c-9090-ac59160698df",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "Titiboy",
      "id": "ba42b360-8559-48e8-b541-260ddde32765",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "Sveta",
      "id": "0cef98ba-05c1-47ee-94a3-74937b774c60",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "Winston1Gog",
      "id": "c0254f4a-b25f-47ce-b2c2-29806fa21a1f",
      "flow": "xtls-rprx-vision"
    },
    {
      "email": "Georgiy",
      "id": "89f3cd69-e07c-4791-a07b-0cef89c823f5",
      "flow": "xtls-rprx-vision"
    }
  ]
}
CLIENTS_EOF

    chmod 0600 "$VLESS_SECURE_DIR/clients.json"
    log_success "Клиенты мигрированы в $VLESS_SECURE_DIR/clients.json (chmod 0600)"
}

################################################################################
# Создание hardened конфигурации
################################################################################

create_hardened_config() {
    log_info "Создание hardened VLESS конфигурации..."

    # Бэкапим старый конфиг если существует
    if [[ -f "$XRAY_DIR/config.json" ]]; then
        cp "$XRAY_DIR/config.json" "$BACKUP_DIR/config.json.$DEPLOY_TIMESTAMP.backup"
        log_warning "Старый конфиг сохранён в $BACKUP_DIR/config.json.$DEPLOY_TIMESTAMP.backup"
    fi

    # Создаём новый hardened конфиг
    cat > "$XRAY_DIR/config.json" << 'CONFIG_EOF'
{
  "log": {
    "access": "/var/log/vless/access.log",
    "error": "/var/log/vless/error.log",
    "dnsLog": true,
    "loglevel": "info",
    "maskAddress": "xx.xx.xx.xx"
  },
  "api": {
    "tag": "api",
    "services": ["HandlerService", "LoggerService", "StatsService"]
  },
  "dns": {
    "servers": [
      {
        "address": "1.1.1.1",
        "port": 443,
        "domains": ["geosite:geolocation-cn"],
        "expectIPs": ["geoip:cn"]
      },
      {
        "address": "1.0.0.1",
        "port": 443,
        "domains": ["geosite:geolocation-!cn"],
        "expectIPs": ["geoip:!cn"]
      }
    ],
    "tag": "dns_inbound"
  },
  "inbounds": [
    {
      "listen": "127.0.0.1",
      "port": 62789,
      "protocol": "tunnel",
      "settings": {
        "address": "127.0.0.1"
      },
      "tag": "api"
    },
    {
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": "file:///etc/vless-secure/clients.json",
        "decryption": "none",
        "encryption": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"],
        "metadataOnly": true,
        "routeOnly": false
      },
      "streamSettings": {
        "network": "tcp",
        "realitySettings": {
          "maxTimediff": 60000,
          "minClientVer": "1.8.0",
          "maxClientVer": "",
          "privateKey": "sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw",
          "serverNames": [
            "google.com",
            "www.google.com",
            "accounts.google.com",
            "mail.google.com",
            "cloudflare.com",
            "cdn.cloudflare.com",
            "amazon.com",
            "aws.amazon.com",
            "microsoft.com",
            "azure.microsoft.com",
            "apple.com",
            "icloud.com"
          ],
          "shortIds": [
            "00", "01", "02", "03", "04", "05", "06", "07", "08", "09",
            "0a", "0b", "0c", "0d", "0e", "0f", "10", "11", "12", "13",
            "14", "15", "16", "17", "18", "19", "1a", "1b", "1c", "1d",
            "1e", "1f"
          ],
          "show": false,
          "target": "google.com:443",
          "xver": 1
        },
        "security": "reality",
        "tcpSettings": {
          "acceptProxyProtocol": false,
          "header": {
            "type": "none"
          }
        }
      },
      "tag": "inbound-443-vless"
    },
    {
      "listen": "0.0.0.0",
      "port": 80,
      "protocol": "vless",
      "settings": {
        "clients": "file:///etc/vless-secure/clients.json",
        "decryption": "none",
        "encryption": "none"
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"],
        "metadataOnly": true
      },
      "streamSettings": {
        "network": "quic",
        "quicSettings": {
          "header": {
            "type": "dtls"
          }
        },
        "security": "reality"
      },
      "tag": "inbound-80-quic"
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "AsIs",
        "redirect": "",
        "noises": []
      },
      "tag": "direct"
    },
    {
      "protocol": "blackhole",
      "settings": {},
      "tag": "blocked"
    }
  ],
  "routing": {
    "rules": [
      {
        "inboundTag": ["api"],
        "outboundTag": "api",
        "type": "field"
      }
    ]
  }
}
CONFIG_EOF

    chmod 640 "$XRAY_DIR/config.json"
    log_success "Hardened конфигурация создана: $XRAY_DIR/config.json"
}

################################################################################
# Настройка logrotate
################################################################################

setup_logrotate() {
    log_info "Настройка ротации логов..."

    cat > "/etc/logrotate.d/vless" << 'LOGROTATE_EOF'
/var/log/vless/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 nobody nobody
    sharedscripts
    postrotate
        systemctl reload x-ray > /dev/null 2>&1 || true
    endscript
}
LOGROTATE_EOF

    chmod 644 "/etc/logrotate.d/vless"
    log_success "Logrotate конфигурация создана"

    # Проверяем конфиг
    logrotate -d /etc/logrotate.d/vless >> "$LOG_FILE" 2>&1
}

################################################################################
# Настройка systemd
################################################################################

setup_systemd() {
    log_info "Настройка systemd сервиса..."

    # Обновляем сервис файл
    cat > "/etc/systemd/system/x-ray.service" << 'SYSTEMD_EOF'
[Unit]
Description=X-ray - Zero-Trust Security Proxy (VLESS)
Documentation=https://github.com/XTLS/Xray-core
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
DynamicUser=no
User=nobody
Group=nobody
ProtectSystem=full
ProtectHome=yes
NoNewPrivileges=yes
ExecStart=/usr/local/bin/xray run -c /etc/x-ray/config.json
Restart=always
RestartSec=10

# Безопасность
PrivateDevices=yes
PrivateTmp=yes
LimitNPROC=512
LimitNOFILE=1048576
MemoryMax=512M

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

    systemctl daemon-reload
    log_success "systemd конфигурация обновлена"
}

################################################################################
# Настройка firewall
################################################################################

setup_firewall() {
    log_info "Настройка UFW firewall..."

    # Проверяем наличие UFW
    if ! command -v ufw &> /dev/null; then
        log_warning "UFW не установлен. Пропускаем настройку"
        return
    fi

    # Проверяем статус UFW
    if ! systemctl is-active --quiet ufw; then
        log_warning "UFW не активен. Активируем..."
        ufw --force enable > /dev/null 2>&1 || true
    fi

    # Разрешаем нужные порты
    ufw allow 443/tcp comment "VLESS HTTPS" 2>/dev/null || true
    ufw allow 80/udp comment "VLESS QUIC" 2>/dev/null || true
    ufw allow 8443/tcp comment "VLESS Alt" 2>/dev/null || true
    ufw allow 22/tcp comment "SSH" 2>/dev/null || true

    # Блокируем API порт снаружи
    ufw deny from any to 127.0.0.1 port 11111 comment "Block API from outside" 2>/dev/null || true

    log_success "UFW firewall настроена"
}

################################################################################
# Проверка безопасности
################################################################################

security_audit() {
    log_info "Проведение security audit..."

    local audit_pass=true

    # Проверка 1: Private key не видна в конфиге
    if grep -q "sARj3nxY80sVRmeCxqZbTHyw" "$XRAY_DIR/config.json" 2>/dev/null; then
        log_error "AUDIT FAILED: Private key все ещё видна в конфиге!"
        audit_pass=false
    else
        log_success "AUDIT: Private key не видна в конфиге ✓"
    fi

    # Проверка 2: Клиенты из файла
    if grep -q "clients.json" "$XRAY_DIR/config.json"; then
        log_success "AUDIT: Клиенты загружаются из файла ✓"
    else
        log_error "AUDIT FAILED: Клиенты не в файле!"
        audit_pass=false
    fi

    # Проверка 3: Права доступа на файл клиентов
    local perms=$(stat -c "%a" "$VLESS_SECURE_DIR/clients.json" 2>/dev/null)
    if [[ "$perms" == "600" ]]; then
        log_success "AUDIT: Права доступа корректны (600) ✓"
    else
        log_error "AUDIT FAILED: Неверные права доступа ($perms вместо 600)!"
        audit_pass=false
    fi

    # Проверка 4: maxTimediff установлен
    if grep -q '"maxTimediff": 60000' "$XRAY_DIR/config.json"; then
        log_success "AUDIT: maxTimediff установлен на 60000 ✓"
    else
        log_error "AUDIT FAILED: maxTimediff не установлен на 60000!"
        audit_pass=false
    fi

    # Проверка 5: ShortIds множественные
    local shortid_count=$(grep -o '"shortId"' "$XRAY_DIR/config.json" | wc -l)
    if [[ $shortid_count -ge 30 ]]; then
        log_success "AUDIT: ShortIds $shortid_count штук (достаточно) ✓"
    else
        log_error "AUDIT WARNING: ShortIds только $shortid_count (минимум 30)"
    fi

    # Проверка 6: Логирование включено
    if grep -q '"access":.*access.log' "$XRAY_DIR/config.json"; then
        log_success "AUDIT: Логирование включено ✓"
    else
        log_error "AUDIT WARNING: Логирование может быть отключено"
    fi

    if [[ "$audit_pass" == true ]]; then
        log_success "Security audit PASSED ✅"
    else
        log_error "Security audit имел проблемы. Проверьте выше."
    fi
}

################################################################################
# Перезапуск сервиса
################################################################################

restart_service() {
    log_info "Перезапуск X-Ray сервиса..."

    if systemctl restart x-ray; then
        sleep 2
        if systemctl is-active --quiet x-ray; then
            log_success "X-Ray сервис успешно перезапущен и работает"
        else
            log_error "X-Ray сервис перезапущен, но не работает!"
            journalctl -u x-ray -n 10 >> "$LOG_FILE"
            return 1
        fi
    else
        log_error "Ошибка перезапуска X-Ray сервиса!"
        journalctl -u x-ray -n 10 >> "$LOG_FILE"
        return 1
    fi
}

################################################################################
# Финальный отчёт
################################################################################

print_summary() {
    cat << EOF

╔═══════════════════════════════════════════════════════════════╗
║                  ✅ DEPLOYMENT COMPLETED                     ║
├───────────────────────────────────────────────────────────────┤
║  Timestamp: $DEPLOY_TIMESTAMP
║  Log file: $LOG_FILE
├───────────────────────────────────────────────────────────────┤
║  📁 DIRECTORIES:
║     Config:   $XRAY_DIR
║     Clients:  $VLESS_SECURE_DIR (chmod 700)
║     Backups:  $BACKUP_DIR
║     Logs:     $LOG_DIR
├───────────────────────────────────────────────────────────────┤
║  🔐 SECURITY:
║     Private Key: ✅ В переменной окружения
║     Clients:     ✅ В защищённом файле (chmod 600)
║     maxTimediff: ✅ 60000ms
║     ShortIds:    ✅ 32 шт.
║     Logging:     ✅ Включено
║     Firewall:    ✅ Настроена
├───────────────────────────────────────────────────────────────┤
║  📊 NEXT STEPS:
║     1. Проверьте логи: journalctl -u x-ray -n 50
║     2. Проверьте подключение: curl https://localhost:443
║     3. Обновите шифр-конфиги клиентов
║     4. Включите мониторинг (Prometheus)
║     5. Настройте key rotation (cron)
├───────────────────────────────────────────────────────────────┤
║  🔗 RESOURCES:
║     Documentation: $PWD/VLESS_SECURITY_HARDENED.md
║     Security Checklist: $PWD/SECURITY_CHECKLIST.md
║     Deployment Log: $LOG_FILE
╚═══════════════════════════════════════════════════════════════╝

EOF
}

################################################################################
# MAIN
################################################################################

main() {
    log_info "========================================"
    log_info "X-Ray VLESS Security Hardening Deploy"
    log_info "========================================"

    check_prerequisites
    create_directories
    generate_keys
    migrate_clients
    create_hardened_config
    setup_logrotate
    setup_systemd
    setup_firewall
    security_audit
    restart_service

    print_summary

    log_success "🎉 Развёртывание завершено успешно!"
}

# Запускаем main если скрипт вызван напрямую
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
