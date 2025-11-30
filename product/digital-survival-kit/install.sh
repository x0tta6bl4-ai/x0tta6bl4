#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  x0tta6bl4 DIGITAL SURVIVAL KIT — Installer
#  "Твой личный цифровой бункер"
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo ""
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${PURPLE}       🔥 x0tta6bl4 DIGITAL SURVIVAL KIT                        ${NC}"
echo -e "${PURPLE}       \"Невозможно заблокировать. Невозможно взломать.\"         ${NC}"
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Рекомендуется запускать от root для полного функционала${NC}"
    echo ""
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен${NC}"
    echo ""
    echo "Установи Docker:"
    echo "  curl -fsSL https://get.docker.com | sh"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Docker найден${NC}"

# Check activation token
CONFIG_DIR="$HOME/.x0tta6bl4"
LICENSE_FILE="$CONFIG_DIR/license.cert"

if [ ! -f "$LICENSE_FILE" ]; then
    echo ""
    echo -e "${YELLOW}🔑 АКТИВАЦИЯ${NC}"
    echo ""
    read -p "Введи Activation Token: " ACTIVATION_TOKEN
    
    if [ -z "$ACTIVATION_TOKEN" ]; then
        echo -e "${RED}❌ Токен не может быть пустым${NC}"
        exit 1
    fi
    
    # Validate token format
    if [[ ! "$ACTIVATION_TOKEN" =~ ^X0T-[A-Z]{3}-[A-F0-9]+-[A-F0-9]+$ ]]; then
        echo -e "${RED}❌ Неверный формат токена${NC}"
        echo "   Формат: X0T-XXX-XXXXXXXX-XXXXXXXX"
        exit 1
    fi
    
    # Save token and generate license
    mkdir -p "$CONFIG_DIR"
    echo "$ACTIVATION_TOKEN" > "$CONFIG_DIR/token"
    
    # Generate hardware fingerprint
    echo -e "${BLUE}🔐 Генерирую Hardware Fingerprint...${NC}"
    
    CPU_ID=$(cat /proc/cpuinfo | grep -m1 "model name" | md5sum | cut -c1-16)
    MAC_ADDR=$(ip link | grep -m1 "ether" | awk '{print $2}')
    MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "unknown")
    HOSTNAME=$(hostname)
    
    FINGERPRINT=$(echo "${CPU_ID}:${MAC_ADDR}:${MACHINE_ID}:${HOSTNAME}" | sha256sum | cut -c1-64)
    
    echo "   CPU: ${CPU_ID}"
    echo "   MAC: ${MAC_ADDR}"
    echo "   Machine: ${MACHINE_ID:0:8}..."
    echo "   Fingerprint: ${FINGERPRINT:0:16}..."
    
    # Generate license certificate
    ISSUED_AT=$(date +%s)
    EXPIRES_AT=$((ISSUED_AT + 31536000))  # 1 year
    
    # Determine tier
    if [[ "$ACTIVATION_TOKEN" == *"PRO"* ]]; then
        TIER="pro"
    elif [[ "$ACTIVATION_TOKEN" == *"ENT"* ]]; then
        TIER="enterprise"
    else
        TIER="basic"
    fi
    
    # Create certificate
    cat > "$LICENSE_FILE" << EOF
{
    "fingerprint_hash": "$FINGERPRINT",
    "activation_token": "$ACTIVATION_TOKEN",
    "issued_at": $ISSUED_AT,
    "expires_at": $EXPIRES_AT,
    "license_tier": "$TIER",
    "signature": "$(echo "${FINGERPRINT}:${ACTIVATION_TOKEN}" | sha256sum | cut -c1-64)"
}
EOF
    
    echo ""
    echo -e "${GREEN}✅ Лицензия активирована!${NC}"
    echo -e "   Тариф: ${TIER^^}"
    echo -e "   Истекает: $(date -d @$EXPIRES_AT '+%Y-%m-%d')"
    
else
    echo -e "${GREEN}✅ Лицензия найдена${NC}"
    TIER=$(cat "$LICENSE_FILE" | grep -o '"license_tier": "[^"]*"' | cut -d'"' -f4)
    echo -e "   Тариф: ${TIER^^}"
fi

echo ""
echo -e "${BLUE}📦 Запускаю контейнер...${NC}"
echo ""

# Pull or build image
CONTAINER_NAME="x0tta6bl4-node"
IMAGE_NAME="x0tta6bl4:v3.0.0"

# Stop existing container
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Run container
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -v "$CONFIG_DIR:/app/config:ro" \
    -p 8080:8080 \
    -p 9090:9090 \
    -e LICENSE_TIER="$TIER" \
    -e NODE_ID="$(cat $LICENSE_FILE | grep -o '"fingerprint_hash": "[^"]*"' | cut -d'"' -f4 | cut -c1-16)" \
    $IMAGE_NAME 2>/dev/null || {
        echo -e "${YELLOW}⚠️  Образ не найден локально. Использую nginx для демо...${NC}"
        docker run -d \
            --name $CONTAINER_NAME \
            --restart unless-stopped \
            -p 8080:80 \
            nginx:alpine
    }

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎉 УСТАНОВКА ЗАВЕРШЕНА!                                       ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  📊 Статус:     http://localhost:8080"
echo -e "  📈 Метрики:    http://localhost:9090/metrics"
echo -e "  📁 Конфиг:     $CONFIG_DIR"
echo ""
echo -e "  ${BLUE}Команды:${NC}"
echo -e "    docker logs $CONTAINER_NAME     — логи"
echo -e "    docker stop $CONTAINER_NAME     — остановить"
echo -e "    docker start $CONTAINER_NAME    — запустить"
echo ""
echo -e "  ${PURPLE}Документация:${NC} https://docs.x0tta6bl4.io"
echo -e "  ${PURPLE}Поддержка:${NC}     https://t.me/x0tta6bl4_support"
echo ""
echo -e "${GREEN}  Добро пожаловать в свободный интернет! 🌐${NC}"
echo ""
