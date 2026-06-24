#!/bin/bash

# Скрипт настройки среды разработки для команды проекта x0tta6bl4
# Версия: 1.0.0
# Дата: Октябрь 2025

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
PROJECT_NAME="x0tta6bl4"
DEV_ENVIRONMENT="development"
PYTHON_VERSION="3.11"
NODE_VERSION="18"
DOCKER_COMPOSE_VERSION="2.23.0"

# Функции логирования
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Проверка операционной системы
check_os() {
    log_info "Определение операционной системы..."

    case "$(uname -s)" in
        Linux*)
            OS="linux"
            ;;
        Darwin*)
            OS="macos"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            OS="windows"
            ;;
        *)
            log_error "Неподдерживаемая операционная система: $(uname -s)"
            exit 1
            ;;
    esac

    log_success "Операционная система: $OS"
}

# Установка базовых инструментов для Linux
install_linux_tools() {
    log_info "Установка базовых инструментов для Linux..."

    # Определение дистрибутива
    if command -v apt-get &> /dev/null; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y \
            curl \
            wget \
            git \
            vim \
            htop \
            tree \
            jq \
            netcat \
            telnet \
            build-essential \
            software-properties-common

    elif command -v yum &> /dev/null; then
        # RHEL/CentOS/Fedora
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y \
            curl \
            wget \
            git \
            vim \
            htop \
            tree \
            jq \
            nc \
            telnet

    elif command -v pacman &> /dev/null; then
        # Arch Linux
        sudo pacman -Syu --noconfirm \
            curl \
            wget \
            git \
            vim \
            htop \
            tree \
            jq \
            netcat \
            inetutils
    fi

    log_success "Базовые инструменты установлены"
}

# Установка базовых инструментов для macOS
install_macos_tools() {
    log_info "Установка базовых инструментов для macOS..."

    # Проверка и установка Homebrew если не установлен
    if ! command -v brew &> /dev/null; then
        log_info "Установка Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi

    # Установка инструментов через Homebrew
    brew install \
        curl \
        wget \
        git \
        vim \
        htop \
        tree \
        jq \
        nc \
        telnet \
        coreutils \
        findutils \
        gnu-sed

    log_success "Базовые инструменты установлены"
}

# Установка Python
install_python() {
    log_info "Установка Python $PYTHON_VERSION..."

    # Проверка существующей установки
    if command -v python$PYTHON_VERSION &> /dev/null; then
        log_info "Python $PYTHON_VERSION уже установлен"
        return
    fi

    case "$OS" in
        linux)
            if command -v apt-get &> /dev/null; then
                sudo apt-get install -y python$PYTHON_VERSION python$PYTHON_VERSION-pip python$PYTHON_VERSION-venv
            elif command -v yum &> /dev/null; then
                sudo yum install -y python$PYTHON_VERSION python$PYTHON_VERSION-pip
            fi
            ;;
        macos)
            brew install python@$PYTHON_VERSION
            ;;
    esac

    log_success "Python $PYTHON_VERSION установлен"
}

# Установка Node.js
install_nodejs() {
    log_info "Установка Node.js $NODE_VERSION..."

    case "$OS" in
        linux)
            curl -fsSL https://deb.nodesource.com/setup_$NODE_VERSION.x | sudo -E bash -
            sudo apt-get install -y nodejs
            ;;
        macos)
            brew install node@$NODE_VERSION
            ;;
    esac

    log_success "Node.js $NODE_VERSION установлен"
}

# Установка Docker и Docker Compose
install_docker() {
    log_info "Установка Docker и Docker Compose..."

    case "$OS" in
        linux)
            # Установка Docker
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER

            # Установка Docker Compose
            sudo curl -L "https://github.com/docker/compose/releases/download/v$DOCKER_COMPOSE_VERSION/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            ;;
        macos)
            brew install --cask docker
            log_warning "Docker Desktop для macOS установлен. Запустите его вручную."
            ;;
    esac

    log_success "Docker установлен"
}

# Установка Kubernetes инструментов
install_k8s_tools() {
    log_info "Установка инструментов Kubernetes..."

    # Установка kubectl
    case "$OS" in
        linux)
            curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
            sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
            ;;
        macos)
            brew install kubectl
            ;;
    esac

    # Установка Helm
    case "$OS" in
        linux)
            curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
            chmod 700 get_helm.sh
            ./get_helm.sh
            ;;
        macos)
            brew install helm
            ;;
    esac

    # Установка k9s (Kubernetes CLI)
    case "$OS" in
        linux)
            curl -sS https://webinstall.dev/k9s | bash
            ;;
        macos)
            brew install k9s
            ;;
    esac

    log_success "Инструменты Kubernetes установлены"
}

# Настройка проекта
setup_project() {
    log_info "Настройка проекта..."

    # Создание директории проекта если не существует
    if [ ! -d "$PROJECT_NAME" ]; then
        git clone https://github.com/your-org/$PROJECT_NAME.git
        cd $PROJECT_NAME
    else
        cd $PROJECT_NAME
    fi

    # Создание виртуального окружения Python
    python$PYTHON_VERSION -m venv venv
    source venv/bin/activate

    # Установка зависимостей разработки
    pip install --upgrade pip
    pip install -r requirements-dev.txt
    pip install -r requirements.txt

    # Установка pre-commit хуков
    if [ -f ".pre-commit-config.yaml" ]; then
        pre-commit install
    fi

    log_success "Проект настроен"
}

# Настройка IDE и редакторов
setup_ide() {
    log_info "Настройка IDE и редакторов..."

    # Установка VS Code расширений (если VS Code установлен)
    if command -v code &> /dev/null; then
        log_info "Установка расширений VS Code..."

        # Python расширения
        code --install-extension ms-python.python
        code --install-extension ms-python.black-formatter
        code --install-extension ms-python.isort
        code --install-extension ms-python.flake8

        # Docker расширения
        code --install-extension ms-azuretools.vscode-docker

        # Kubernetes расширения
        code --install-extension ms-kubernetes-tools.vscode-kubernetes-tools

        # Дополнительные полезные расширения
        code --install-extension eamodio.gitlens
        code --install-extension ms-vscode.vscode-json
        code --install-extension redhat.vscode-yaml
        code --install-extension ms-vscode.powershell

        log_success "Расширения VS Code установлены"
    else
        log_warning "VS Code не найден. Установите VS Code для автоматической настройки расширений."
    fi

    # Настройка Vim (если используется)
    if command -v vim &> /dev/null; then
        log_info "Настройка Vim..."

        # Создание базового .vimrc если не существует
        if [ ! -f ~/.vimrc ]; then
            cat > ~/.vimrc << 'EOF'
set number
set tabstop=4
set shiftwidth=4
set expandtab
set autoindent
set smartindent
set showmatch
set ruler
set incsearch
set hlsearch
syntax on
filetype indent on

" Python настройки
autocmd FileType python setlocal tabstop=4 shiftwidth=4 expandtab

" JSON настройки
autocmd FileType json setlocal tabstop=2 shiftwidth=2 expandtab
EOF
        fi

        log_success "Vim настроен"
    fi
}

# Создание полезных скриптов разработки
create_dev_scripts() {
    log_info "Создание полезных скриптов разработки..."

    mkdir -p ~/bin

    # Скрипт быстрого запуска проекта
    cat > ~/bin/dev-start << 'EOF'
#!/bin/bash
cd ~/projects/x0tta6bl4
source venv/bin/activate
make up
EOF

    # Скрипт быстрого тестирования
    cat > ~/bin/dev-test << 'EOF'
#!/bin/bash
cd ~/projects/x0tta6bl4
source venv/bin/activate
make test
EOF

    # Скрипт быстрого развертывания
    cat > ~/bin/dev-deploy << 'EOF'
#!/bin/bash
cd ~/projects/x0tta6bl4
source venv/bin/activate
make deploy-dev
EOF

    chmod +x ~/bin/dev-*

    # Добавление ~/bin в PATH если не добавлено
    if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
        echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
        log_info "Добавлен ~/bin в PATH"
    fi

    log_success "Скрипты разработки созданы"
}

# Настройка Git
setup_git() {
    log_info "Настройка Git..."

    # Проверка настройки Git
    if ! git config --global user.name &>/dev/null; then
        log_info "Настройка глобальной конфигурации Git..."
        read -p "Введите ваше имя для Git: " git_name
        read -p "Введите ваш email для Git: " git_email

        git config --global user.name "$git_name"
        git config --global user.email "$git_email"

        # Дополнительные настройки Git
        git config --global core.editor vim
        git config --global init.defaultBranch main
        git config --global pull.rebase false
        git config --global fetch.prune true

        log_success "Git настроен"
    else
        log_info "Git уже настроен"
    fi
}

# Создание файла README для настройки
create_setup_readme() {
    log_info "Создание руководства по настройке..."

    cat > DEVELOPMENT_SETUP.md << 'EOF'
# Руководство по настройке среды разработки x0tta6bl4

## Быстрый старт

1. **Запуск проекта:**
   ```bash
   dev-start
   ```

2. **Запуск тестов:**
   ```bash
   dev-test
   ```

3. **Развертывание в development:**
   ```bash
   dev-deploy
   ```

## Установленные инструменты

### Основные инструменты разработки:
- **Python 3.11** - основной язык разработки
- **Node.js 18** - для frontend инструментов
- **Docker & Docker Compose** - для контейнеризации
- **kubectl** - для работы с Kubernetes
- **Helm** - для управления релизами
- **k9s** - улучшенный CLI для Kubernetes

### IDE и редакторы:
- **VS Code** с расширениями для Python, Docker, Kubernetes
- **Vim** с настройками для разработки

### Скрипты разработки:
- `dev-start` - быстрый запуск проекта
- `dev-test` - запуск тестов
- `dev-deploy` - развертывание в development

## Структура проекта

```
x0tta6bl4/
├── x0tta6bl4/           # Основной код приложения
├── tests/               # Тесты
├── docs/                # Документация
├── k8s-manifests/       # Kubernetes манифесты
├── ci-cd/               # CI/CD скрипты
├── requirements*.txt     # Зависимости Python
└── infrastructure/      # Инфраструктурные скрипты
```

## Рабочий процесс разработки

### 1. Создание новой функции:
```bash
git checkout -b feature/new-feature
# Разработка
make test
git add .
git commit -m "feat: add new feature"
git push origin feature/new-feature
```

### 2. Локальное тестирование:
```bash
make up          # Запуск локальных сервисов
make test        # Запуск тестов
make down        # Остановка сервисов
```

### 3. Развертывание в development:
```bash
make deploy-dev  # Развертывание в Kubernetes development
```

### 4. Мониторинг:
```bash
kubectl get pods -n development
k9s -n development  # Интерактивный мониторинг
```

## Полезные команды

### Kubernetes:
```bash
kubectl get all -n development
kubectl logs -f deployment/x0tta6bl4 -n development
kubectl port-forward svc/x0tta6bl4 8080:80 -n development
```

### Docker:
```bash
docker-compose ps
docker-compose logs -f app
docker-compose exec app bash
```

### Мониторинг:
```bash
# Prometheus
kubectl port-forward -n development svc/prometheus-kube-prometheus-prometheus 9090:9090

# Grafana
kubectl port-forward -n development svc/prometheus-grafana 3000:80

# Jaeger
kubectl port-forward -n development svc/jaeger-all-in-one 16686:16686
```

## Рекомендации

1. **Используйте виртуальное окружение** для изоляции зависимостей
2. **Запускайте тесты** перед каждым коммитом
3. **Проверяйте код** линтерами перед отправкой в репозиторий
4. **Используйте k9s** для удобного мониторинга кластера
5. **Документируйте изменения** в коде и конфигурации

## Поддержка

При возникновении проблем обращайтесь к:
- Техническому руководителю проекта
- DevOps команде
- Документации в папке `docs/`
EOF

    log_success "Руководство по настройке создано"
}

# Основная функция
main() {
    log_info "Настройка среды разработки для проекта x0tta6bl4"
    echo "==============================================="

    check_os

    case "$OS" in
        linux)
            install_linux_tools
            ;;
        macos)
            install_macos_tools
            ;;
    esac

    install_python
    install_nodejs
    install_docker
    install_k8s_tools
    setup_git
    setup_ide
    create_dev_scripts
    create_setup_readme

    log_success "Настройка среды разработки завершена успешно!"
    echo
    log_info "Следующие шаги:"
    echo "1. Перезагрузите терминал или выполните: source ~/.bashrc"
    echo "2. Смените пользователя в группу docker: sudo usermod -aG docker \$USER"
    echo "3. Изучите руководство: cat DEVELOPMENT_SETUP.md"
    echo "4. Начните работу с проектом: dev-start"
    echo
    log_info "Среда разработки готова к использованию!"
}

# Запуск основной функции
main "$@"