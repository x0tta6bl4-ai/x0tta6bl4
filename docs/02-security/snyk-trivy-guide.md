# 🛡️ **Полная интеграция Snyk и Trivy в CI для мгновенного HTML-отчёта по уязвимостям**

## 📋 **Обзор решения**

**Ключевая рекомендация:** объединить запуск Snyk и Trivy в едином скрипте, генерировать промежуточные JSON-отчёты и конвертировать их в HTML с помощью `snyk-to-html` и `trivy-html-report`, а затем публиковать единый артефакт в CI (GitLab CI, GitHub Actions или Jenkins).

---

## 🔧 **1. Предварительные требования**

### **Snyk CLI установка и аутентификация:**
```bash
npm install -g snyk
export SNYK_TOKEN=<ваш_токен>  # либо через секреты CI-системы
snyk auth $SNYK_TOKEN
```

### **Snyk JSON → HTML конвертер:**
```bash
npm install -g snyk-to-html
```

### **Trivy установка:**
```bash
# Пример для Linux:
sudo apt-get update && sudo apt-get install -y wget
wget https://github.com/aquasecurity/trivy/releases/latest/download/trivy_$(uname -s)_$(uname -m).tar.gz
tar zxvf trivy_*.tar.gz trivy -C /usr/local/bin
```

### **Trivy JSON → HTML конвертер:**
```bash
git clone https://github.com/andres-dev4/trivy-html-report.git
pip install -r trivy-html-report/requirements.txt
pip install -e trivy-html-report  # для CLI trivy-html-report
```

---

## 🚀 **2. Скрипт объединённого сканирования `security-scan.sh`**

```bash
#!/usr/bin/env bash
set -eo pipefail

# Параметры по умолчанию
RUN_SNYK=false; RUN_TRIVY=false
SEVERITY="HIGH"; OUTPUT="security-report.html"
IMAGE_TAG="my-image:latest"

# Разбор флагов
while [[ $# -gt 0 ]]; do
  case $1 in
    --snyk)      RUN_SNYK=true; shift ;;
    --trivy)     RUN_TRIVY=true; shift ;;
    --severity)  SEVERITY=$2; shift 2 ;;
    --image)     IMAGE_TAG=$2; shift 2 ;;
    --output)    OUTPUT=$2; shift 2 ;;
    *)           echo "Неизвестный параметр: $1"; exit 1 ;;
  esac
done

WORKDIR=$(pwd)/scan-results
mkdir -p "$WORKDIR"

# 2.1 Snyk: тест → JSON → HTML
if [ "$RUN_SNYK" = true ]; then
  echo "Запуск Snyk..."
  snyk test --json > "$WORKDIR/snyk-report.json"  # Выполняет анализ кода и зависимостей в формате JSON
  snyk-to-html -i "$WORKDIR/snyk-report.json" -o "$WORKDIR/snyk-report.html"  # Конвертация в HTML
fi

# 2.2 Trivy: скан образа → JSON → HTML
if [ "$RUN_TRIVY" = true ]; then
  echo "Запуск Trivy..."
  trivy image \
    --ignore-unfixed \
    --severity "$SEVERITY" \
    --format json \
    -o "$WORKDIR/trivy-report.json" "$IMAGE_TAG"  # Генерирует JSON-отчёт по CVE в контейнере
  trivy-html-report \
    --input-json "$WORKDIR/trivy-report.json" \
    --output-html "$WORKDIR/trivy-report.html"  # Конвертация Trivy JSON в HTML
fi

# 2.3 Сборка итогового отчёта
{
  echo "<html><body>"
  [ -f "$WORKDIR/snyk-report.html" ] && sed -n '/<body>/,/<\/body>/p' "$WORKDIR/snyk-report.html"
  [ -f "$WORKDIR/trivy-report.html" ] && sed -n '/<body>/,/<\/body>/p' "$WORKDIR/trivy-report.html"
  echo "</body></html>"
} > "$WORKDIR/$OUTPUT"

echo "Отчёт собран: $WORKDIR/$OUTPUT"
```

---

## ⚙️ **3. Интеграция в GitLab CI**

```yaml
stages:
  - security_scan

security_scan:
  image: docker:stable
  services:
    - docker:dind
  variables:
    DOCKER_TLS_CERTDIR: ""
  before_script:
    - apk add --no-cache bash curl npm python3 py3-pip git
    - npm install -g snyk-to-html
    - pip3 install -e trivy-html-report
    - curl -sL https://github.com/aquasecurity/trivy/releases/latest/download/trivy_$(uname -s)_$(uname -m).tar.gz | tar zx -C /usr/local/bin
    - curl -sL https://github.com/snyk/snyk/releases/latest/download/snyk-linux.tar.gz | tar zx -C /usr/local/bin
    - snyk auth "$SNYK_TOKEN"  # из секретов проекта
  script:
    - chmod +x security-scan.sh
    - ./security-scan.sh --snyk --trivy --severity HIGH --image "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA" --output security-report.html
  artifacts:
    paths:
      - scan-results/security-report.html
    expire_in: 1 week
```

---

## 🔄 **4. Интеграция в GitHub Actions**

```yaml
name: Security Scan

on:
  push:

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      # Установка инструментов
      - name: Set up Snyk
        uses: snyk/actions/node@master  # Snyk GH Action
        with:
          args: --severity-threshold=high --json-file-output=snyk-report.json

      - name: Convert Snyk report to HTML
        run: snyk-to-html -i snyk-report.json -o snyk-report.html

      - name: Set up Trivy
        uses: aquasecurity/trivy-action@0.28.0  # Trivy GH Action
        with:
          image-ref: ${{ github.repository }}:${{ github.sha }}
          format: json
          output: trivy-report.json
          ignore-unfixed: true
          severity: CRITICAL,HIGH

      - name: Convert Trivy report to HTML
        run: trivy-html-report --input-json trivy-report.json --output-html trivy-report.html

      - name: Merge reports
        run: |
          echo "<html><body>" > combined-report.html
          sed -n '/<body>/,/<\/body>/p' snyk-report.html >> combined-report.html
          sed -n '/<body>/,/<\/body>/p' trivy-report.html >> combined-report.html
          echo "</body></html>" >> combined-report.html

      - name: Upload report
        uses: actions/upload-artifact@v3
        with:
          name: security-report
          path: combined-report.html
```

---

## ⚡ **5. Основные преимущества интеграции**

### **🎯 Комплексное покрытие:**
- **Snyk**: Анализ зависимостей, контейнеров и инфраструктуры как кода
- **Trivy**: Уязвимости в OS-пакетах, секреты, misconfiguration

### **📊 Единый отчёт:**
- Объединённый HTML-отчёт с результатами обоих сканеров
- JSON-формат для программной обработки
- Артефакты CI для долгосрочного хранения

### **🔄 Автоматизация:**
- Автоматический запуск при каждом коммите
- Интеграция в существующие CI/CD пайплайны
- Гибкая настройка через параметры скрипта

---

## 🚨 **6. Типичные ошибки и их решение**

### **Snyk ошибки:**
- **SNYK-0005**: Неверный `SNYK_TOKEN` → Проверить токен и permissions
- **SNYK-0006**: Rate limiting → Снизить частоту запусков или обновить план
- **SNYK-CLI-0009**: Too many vulnerable paths → Использовать `--detection-depth` и `--exclude`

### **Trivy ошибки:**
- **Docker daemon connection**: Монтировать `/var/run/docker.sock` или использовать `docker:dind`
- **Timeout errors**: Увеличить `--timeout` для крупных образов
- **Rate limiting**: Задать `GITHUB_TOKEN` для GitHub API

---

## 📈 **7. Рекомендации по оптимизации**

### **Производительность:**
- Кэшировать базы данных между запусками
- Использовать параллельное выполнение Snyk и Trivy
- Оптимизировать размер Docker-образов

### **Безопасность:**
- Хранить токены в секретах CI/CD
- Регулярно обновлять базы уязвимостей
- Настроить автоматические уведомления о критических CVE

### **Мониторинг:**
- Отслеживать метрики покрытия сканирования
- Анализировать тренды уязвимостей
- Интегрировать с системами управления инцидентами

---

## ✅ **Результат**

В результате в артефактах CI появится **security-report.html** с объединённым отчётом Snyk и Trivy, готовым к мгновенному просмотру и анализу командой безопасности.