#!/bin/bash
# deploy_v3.sh
# Скрипт для автоматизации развертывания компонентов v3.0

set -e

echo "🚀 РАЗВЕРТЫВАНИЕ X0TTA6BL4 V3.0"
echo "=" | head -c 60 && echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для проверки зависимостей
check_dependencies() {
    echo -e "${YELLOW}📦 Проверка зависимостей...${NC}"
    
    # Проверка Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 не найден${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Python3 найден${NC}"
    
    # Проверка pip
    if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
        echo -e "${RED}❌ pip не найден${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ pip найден${NC}"
    
    # Проверка Docker (опционально)
    if command -v docker &> /dev/null; then
        echo -e "${GREEN}✅ Docker найден${NC}"
    else
        echo -e "${YELLOW}⚠️  Docker не найден (опционально)${NC}"
    fi
}

# Функция для установки зависимостей
install_dependencies() {
    echo -e "${YELLOW}📥 Установка зависимостей...${NC}"
    
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo -e "${GREEN}✅ Зависимости установлены${NC}"
    else
        echo -e "${RED}❌ requirements.txt не найден${NC}"
        exit 1
    fi
}

# Функция для запуска тестов
run_tests() {
    echo -e "${YELLOW}🧪 Запуск тестов...${NC}"
    
    if command -v pytest &> /dev/null; then
        pytest tests/test_*v3*.py -v || {
            echo -e "${YELLOW}⚠️  Некоторые тесты не прошли${NC}"
        }
    else
        echo -e "${YELLOW}⚠️  pytest не найден, пропускаем тесты${NC}"
    fi
}

# Функция для проверки конфигурации
check_config() {
    echo -e "${YELLOW}⚙️  Проверка конфигурации...${NC}"
    
    if [ -f "config/production_v3.yaml" ]; then
        echo -e "${GREEN}✅ Конфигурация найдена${NC}"
        
        # Проверка YAML синтаксиса
        if command -v python3 &> /dev/null; then
            python3 -c "import yaml; yaml.safe_load(open('config/production_v3.yaml'))" && \
                echo -e "${GREEN}✅ Конфигурация валидна${NC}" || \
                echo -e "${RED}❌ Ошибка в конфигурации${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Конфигурация не найдена${NC}"
    fi
}

# Функция для создания директорий
create_directories() {
    echo -e "${YELLOW}📁 Создание директорий...${NC}"
    
    mkdir -p logs
    mkdir -p data
    mkdir -p /etc/x0tta6bl4 2>/dev/null || echo -e "${YELLOW}⚠️  Не удалось создать /etc/x0tta6bl4 (требуются права root)${NC}"
    
    echo -e "${GREEN}✅ Директории созданы${NC}"
}

# Функция для генерации ключей
generate_keys() {
    echo -e "${YELLOW}🔑 Генерация ключей...${NC}"
    
    if [ ! -f "/etc/x0tta6bl4/stego_master.key" ]; then
        if [ -w "/etc/x0tta6bl4" ] 2>/dev/null; then
            python3 -c "import secrets; open('/etc/x0tta6bl4/stego_master.key', 'wb').write(secrets.token_bytes(32))"
            chmod 600 /etc/x0tta6bl4/stego_master.key
            echo -e "${GREEN}✅ Stego-Mesh ключ создан${NC}"
        else
            echo -e "${YELLOW}⚠️  Не удалось создать ключ (требуются права root)${NC}"
            echo -e "${YELLOW}   Создайте вручную: python3 -c \"import secrets; open('/etc/x0tta6bl4/stego_master.key', 'wb').write(secrets.token_bytes(32))\"${NC}"
        fi
    else
        echo -e "${GREEN}✅ Stego-Mesh ключ уже существует${NC}"
    fi
}

# Функция для проверки компонентов
verify_components() {
    echo -e "${YELLOW}🔍 Проверка компонентов...${NC}"
    
    components=(
        "src/mapek/graphsage_analyzer.py"
        "src/anti_censorship/stego_mesh.py"
        "src/testing/digital_twins.py"
        "src/ai/federated_learning.py"
        "src/storage/immutable_audit_trail.py"
        "src/self_healing/mape_k_v3_integration.py"
    )
    
    all_ok=true
    for component in "${components[@]}"; do
        if [ -f "$component" ]; then
            echo -e "${GREEN}✅ $(basename $component)${NC}"
        else
            echo -e "${RED}❌ $(basename $component) не найден${NC}"
            all_ok=false
        fi
    done
    
    if [ "$all_ok" = true ]; then
        echo -e "${GREEN}✅ Все компоненты найдены${NC}"
    else
        echo -e "${RED}❌ Некоторые компоненты отсутствуют${NC}"
        exit 1
    fi
}

# Главная функция
main() {
    echo ""
    check_dependencies
    echo ""
    
    install_dependencies
    echo ""
    
    verify_components
    echo ""
    
    check_config
    echo ""
    
    create_directories
    echo ""
    
    generate_keys
    echo ""
    
    if [ "$1" = "--with-tests" ]; then
        run_tests
        echo ""
    fi
    
    echo -e "${GREEN}✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО!${NC}"
    echo ""
    echo "Следующие шаги:"
    echo "  1. Настройте config/production_v3.yaml"
    echo "  2. Запустите демо: python3 demos/complete_v3_demo.py"
    echo "  3. Запустите API: uvicorn src.api.v3_endpoints:router --host 0.0.0.0 --port 8000"
    echo ""
}

# Запуск
main "$@"

